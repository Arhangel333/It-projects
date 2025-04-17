import bpy
import math
import numpy as np
import taichi as ti
import bmesh

# Инициализация Taichi с поддержкой Vulkan
ti.init(arch=ti.vulkan)

# Константы
PARTICLE_COUNT = 2
CYLINDER_RADIUS = 3.0
CYLINDER_HEIGHT = 15.0

cylinder_obj = None


# Taichi поля
particles_pos = ti.Vector.field(3, dtype=ti.f32, shape=PARTICLE_COUNT)
density_field = ti.field(dtype=ti.f32, shape=PARTICLE_COUNT)  # Явно указана форма

def clear_scene():
    # Удаляем все обработчики перед очисткой сцены
    for handler in bpy.app.handlers.frame_change_pre[:]:
        if "update_density" in handler.__name__:
            bpy.app.handlers.frame_change_pre.remove(handler)
    
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def create_hollow_cylinder(radius=3.0, height=5.0, thickness=0.5):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height)
    outer = bpy.context.object
    outer.name = "Outer_Cylinder"
    
    if outer and outer.type == 'MESH':
    # Переходим в режим редактирования
        bpy.ops.object.mode_set(mode='EDIT')
        mesh = bmesh.from_edit_mesh(outer.data)
         # Выбираем все полигоны
        bpy.ops.mesh.select_all(action='SELECT')
        
        # Переключаемся в режим вершин (чтобы корректно выделить грани)
        bpy.ops.mesh.select_mode(type='FACE')
        
        # Выделяем только полигоны, перпендикулярные оси Z (верх/низ)
        for face in mesh.faces:
            normal = face.normal
            if abs(normal.z) > 0.99:  # Если нормаль почти по Z (верх/низ)
                face.select = True
            else:
                face.select = False
        
        # Удаляем выделенные полигоны (верх и низ)
        bpy.ops.mesh.delete(type='FACE')
        
        # Обновляем сетку
        bmesh.update_edit_mesh(outer.data)
        
        # Возвращаемся в объектный режим
        bpy.ops.object.mode_set(mode='OBJECT')
        
        print("Круглые полигоны удалены, осталась только боковая поверхность!")
    else:
        print("Активный объект не является мешем или не выбран!")
    
    outer.modifiers.new(name="Collision", type='COLLISION')

    #bpy.data.objects.remove(inner)
    
    outer.name = "Hollow_Cylinder"
    
    # Инициализируем поле плотности по количеству вершин
    density_field = ti.field(dtype=ti.f32, shape=len(outer.data.vertices))
    return outer

@ti.kernel
def update_particles(particles: ti.types.ndarray(dtype=ti.math.vec3), 
                   wind: ti.math.vec3,
                   speed: ti.f32):  # Добавляем параметр скорости
    for i in range(particles.shape[0]):
        pos = particles[i]
        velocity = wind * speed + ti.Vector([ti.random()*0.1-0.05 for _ in range(3)])
        pos += velocity * 0.1  # Уменьшаем шаг для стабильности
        
        # Ограничение движения внутри цилиндра
        if pos.z > CYLINDER_HEIGHT/2:
            pos.z = -CYLINDER_HEIGHT/2
        if pos.y > CYLINDER_HEIGHT/2:
            pos.y = -CYLINDER_HEIGHT/2
        
        particles_pos[i] = pos
        particles[i] = pos

@ti.kernel
def calculate_density(vertices: ti.types.ndarray(dtype=ti.math.vec3), 
                     density_out: ti.types.ndarray(dtype=ti.f32)):
    for i in range(vertices.shape[0]):
        vert_pos = vertices[i]
        density = 0.0
        
        for j in range(PARTICLE_COUNT):
            dist = (vert_pos - particles_pos[j]).norm()
            density += ti.exp(-dist * 2.0)
            
        density_out[i] = density

def setup_density_visualization(cylinder):
    global cylinder_obj
    cylinder_obj = cylinder  # Сохраняем ссылку
    print(f"check\n")
    # Удаляем старый атрибут если существует
    if "density" in cylinder.data.attributes:
        cylinder.data.attributes.remove(cylinder.data.attributes["density"])
    
    # Создаем новый атрибут
    density_attr = cylinder.data.attributes.new(name="density", type='FLOAT', domain='POINT')
    
    # Создаем материал
    if "DensityMaterial" not in bpy.data.materials:
        mat = bpy.data.materials.new(name="DensityMaterial")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()
        
        # Настройка нод материала
        attr = nodes.new('ShaderNodeAttribute')
        attr.attribute_name = "density"
        
        map_range = nodes.new('ShaderNodeMapRange')
        map_range.inputs['From Min'].default_value = 0.0
        map_range.inputs['From Max'].default_value = 1.0
        
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (0, 0, 1, 1)
        ramp.color_ramp.elements[1].color = (1, 0, 0, 1)
        
        output = nodes.new('ShaderNodeOutputMaterial')
        principled = nodes.new('ShaderNodeBsdfPrincipled')
        
        # Соединяем ноды
        links = mat.node_tree.links
        links.new(attr.outputs['Fac'], map_range.inputs['Value'])
        links.new(map_range.outputs['Result'], ramp.inputs['Fac'])
        links.new(ramp.outputs['Color'], principled.inputs['Base Color'])
        links.new(principled.outputs['BSDF'], output.inputs['Surface'])
    else:
        mat = bpy.data.materials["DensityMaterial"]
    
    # Назначаем материал
    if cylinder.data.materials:
        cylinder.data.materials[0] = mat
    else:
        cylinder.data.materials.append(mat)

def update_density(scene):
    global cylinder_obj
    
    # Проверяем, что объекты существуют
    if not cylinder_obj or not cylinder_obj.name in bpy.data.objects:
        return
    
    emitter = bpy.data.objects.get("Particle_Emitter")
    if not emitter or not emitter.particle_systems:
        return
        
    if emitter.particle_systems[0].settings.render_type == 'OBJECT':
        for dup in bpy.data.objects:
            print(f"Координаты\n")
            if dup.instance_type == 'PARTICLES':
                
                print(f"Instance at: {dup.location}")
                print(f"Координаты\n")

    '''
    particles = emitter.particle_systems[0].particles
    part_data = np.empty((PARTICLE_COUNT, 3), dtype=np.float32)
    print(f"check23 Count {emitter.particle_systems[0].settings.count }\n")
    for i in range(PARTICLE_COUNT):
        p = particles[i]
        print(f"Частица: location={p.location}")  # Вывод вектора целиком
        print(f"Координаты: X={p.location.x}, Y={p.location.y}, Z={p.location.z}")
    
    
    print(f"check2\n")
    for i, p in enumerate(particles):
        part_data[i] = p.location
        print(f"check23\n")
        print(f"Particle {i} location: {p.location}")
    print(f"check3\n")
    verts = np.empty((len(cylinder_obj.data.vertices), 3), dtype=np.float32)
    cylinder_obj.data.vertices.foreach_get("co", verts.ravel())
    density = np.empty(len(cylinder_obj.data.vertices), dtype=np.float32)
    
    update_particles(part_data, ti.math.vec3(0, 0, 0.5), 500.0)
    calculate_density(verts, density)
    
    # Обновляем атрибут
    density_attr = cylinder_obj.data.attributes["density"]
    for i, val in enumerate(density):
        density_attr.data[i].value = val
    
    cylinder_obj.data.update()


    '''


def main():
    clear_scene()


    # Удаляем старые обработчики перед запуском
    for handler in bpy.app.handlers.frame_change_pre[:]:
        if "update_density" in handler.__name__:
            bpy.app.handlers.frame_change_pre.remove(handler)



    #bpy.context.window.workspace = bpy.data.workspaces["Скриптинг"]
    # Создаем объекты
    cylinder = create_hollow_cylinder(CYLINDER_RADIUS, CYLINDER_HEIGHT)
    bpy.ops.transform.rotate(value=math.pi/2.0, orient_axis='Y', orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', constraint_axis=(False, True, False), mirror=False, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'INCREMENT'}, use_snap_project=False, snap_target='CLOSEST', use_snap_self=True, use_snap_edit=True, use_snap_nonedit=True, use_snap_selectable=False)
    mod = cylinder.modifiers.new(name="Subdivision", type='SUBSURF')
    mod.levels = 2  # Количество уровней подразделения (в режиме просмотра)
    mod.render_levels = 2  # Количество уровней при рендере

    # Применяем модификатор (если нужно сразу получить результат)
    bpy.ops.object.modifier_apply(modifier="Subdivision")

    bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=(0, 0, -1.5), scale=(1, 5, 1.5))
    cube = bpy.context.object
    cube.modifiers.new(name="Collision", type='COLLISION')

    bpy.ops.mesh.primitive_plane_add(size=CYLINDER_RADIUS*2, rotation=(math.pi/2.0, 0, math.pi/2.0), location=(-CYLINDER_HEIGHT/2 - 0.5, 0, 0))
    emitter = bpy.context.object
    emitter.name = "Particle_Emitter"
    
    
    psys = emitter.modifiers.new(name="Particles", type='PARTICLE_SYSTEM').particle_system
    settings = psys.settings
    settings.count = PARTICLE_COUNT
    settings.lifetime = 100
    settings.emit_from = 'FACE'
    settings.physics_type = 'NEWTON'
    settings.normal_factor = 10
    settings.frame_start = 1

    bpy.ops.ptcache.bake_all(bake=True)
    bpy.context.scene.frame_set(int(settings.frame_start) + 1)

    print(len(psys.particles), "COUNT TOO\n")
    setup_density_visualization(cylinder)
   
    # Камера и свет
    bpy.ops.object.camera_add(location=(-2.97332, -33.2669, 3.56712), rotation=(math.radians(82.8666), math.radians(-0.000004), math.radians(-3.26668)))
    bpy.context.scene.camera = bpy.context.object
    
    bpy.ops.object.light_add(type='SUN', location=(15, -15, 20))
    print(settings.count, "COUNT\n")
    # Добавляем новый обработчик
    bpy.app.handlers.frame_change_pre.append(update_density)
    
    print("Сцена готова! Нажмите пробел для запуска анимации")

if __name__ == "__main__":
    main()
