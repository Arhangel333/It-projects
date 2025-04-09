import bpy
import math
import numpy as np
import taichi as ti

# Инициализация Taichi с поддержкой Vulkan
ti.init(arch=ti.vulkan)

# Константы
PARTICLE_COUNT = 2000
CYLINDER_RADIUS = 3.0
CYLINDER_HEIGHT = 5.0

# Taichi поля
particles_pos = ti.Vector.field(3, dtype=ti.f32, shape=PARTICLE_COUNT)
density_field = ti.field(dtype=ti.f32)

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def create_hollow_cylinder(radius=3.0, height=5.0, thickness=0.5):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height)
    outer = bpy.context.object
    outer.name = "Outer_Cylinder"
    
    bpy.ops.mesh.primitive_cylinder_add(radius=radius-thickness, depth=height+0.2)
    inner = bpy.context.object
    
    bool_mod = outer.modifiers.new(name="Bool", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = inner
    bpy.ops.object.modifier_apply(modifier="Bool")
    bpy.data.objects.remove(inner)
    
    outer.name = "Hollow_Cylinder"
    
    # Инициализируем поле плотности по количеству вершин
    density_field = ti.field(dtype=ti.f32, shape=len(outer.data.vertices))
    return outer

@ti.kernel
def update_particles(particles: ti.types.ndarray(dtype=ti.math.vec3), wind: ti.math.vec3):
    for i in range(particles.shape[0]):
        pos = particles[i]
        pos += wind + ti.Vector([ti.random()*0.1-0.05 for _ in range(3)])
        
        # Ограничение движения внутри цилиндра
        if pos.z > CYLINDER_HEIGHT/2:
            pos.z = -CYLINDER_HEIGHT/2
        
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
    # Создаем атрибут плотности
    cylinder.data.attributes.new(name="density", type='FLOAT', domain='POINT')
    
    # Создаем материал
    mat = bpy.data.materials.new(name="DensityMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    # Настраиваем ноды материала
    attr = nodes.new('ShaderNodeAttribute')
    attr.attribute_name = "density"
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0,0,1,1)
    ramp.color_ramp.elements[1].color = (1,0,0,1)
    
    output = nodes.new('ShaderNodeOutputMaterial')
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    
    # Соединяем ноды
    links = mat.node_tree.links
    links.new(attr.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], principled.inputs['Base Color'])
    links.new(principled.outputs['BSDF'], output.inputs['Surface'])
    
    cylinder.data.materials.append(mat)
    
    # Обработчик кадров
    def update_density(scene):
        particles = bpy.data.objects["Particle_Emitter"].particle_systems[0].particles
        part_data = np.empty((PARTICLE_COUNT, 3), dtype=np.float32)
        
        for i, p in enumerate(particles):
            part_data[i] = p.location
        
        verts = np.empty((len(cylinder.data.vertices), 3), dtype=np.float32)
        cylinder.data.vertices.foreach_get("co", verts.ravel())
        density = np.empty(len(cylinder.data.vertices), dtype=np.float32)
        
        update_particles(part_data, ti.math.vec3(0,0,0.5))
        calculate_density(verts, density)
        
        # Обновляем атрибут
        density_attr = cylinder.data.attributes["density"]
        for i, val in enumerate(density):
            density_attr.data[i].value = val
    
    bpy.app.handlers.frame_change_pre.append(update_density)

def main():
    clear_scene()
    
    # Создаем объекты
    cylinder = create_hollow_cylinder(CYLINDER_RADIUS, CYLINDER_HEIGHT)
    bpy.ops.mesh.primitive_plane_add(size=CYLINDER_RADIUS*2)
    emitter = bpy.context.object
    emitter.name = "Particle_Emitter"
    emitter.location.z = -CYLINDER_HEIGHT/2 - 0.5
    emitter.rotation_euler.x = math.pi/2
    
    # Настраиваем частицы
    psys = emitter.modifiers.new(name="Particles", type='PARTICLE_SYSTEM').particle_system
    settings = psys.settings
    settings.count = PARTICLE_COUNT
    settings.lifetime = 100
    settings.emit_from = 'FACE'
    settings.physics_type = 'NEWTON'
    
    # Настраиваем визуализацию плотности
    setup_density_visualization(cylinder)
    
    # Камера и свет
    bpy.ops.object.camera_add(location=(10, -10, 5))
    bpy.context.scene.camera = bpy.context.object
    
    bpy.ops.object.light_add(type='SUN', location=(15, -15, 20))
    
    print("Сцена готова! Нажмите пробел для запуска анимации")

if __name__ == "__main__":
    main()