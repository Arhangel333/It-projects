Последняя версия кода в actualcode.py  
  

PYTHON INTERACTIVE CONSOLE 3.11.11  
Чтобы запустить проект:  

**1** Скачайте Miniconda c официального сайта https://docs.conda.io/en/latest/miniconda.html (если нужно)  
или выполните в cmd:  
curl -o Miniconda3-installer.exe https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe  
    start /wait Miniconda3-installer.exe /InstallationType=JustMe /AddToPath=1 /S  
    del Miniconda3-installer.exe  
      
**2** В cmd перейдите в директорию где находится наш проект и файл окружения environment.yml   

**3** Выполните команду для активации окружения из environment.yml в cmd при помощи conda(Miniconda)  
C:\Users\azhim\miniconda3\_conda.exe env create -f environment.yml  
C:\Users\azhim\miniconda3\scripts\activate blender_project  
"путь к исполняемому файлу блендера" проект.blend --python scripts\script.py  
где  
    проект.blend - проект блендера который мы хотим запустить  
    scripts\script.py - путь к скрипту который мы хотим запустить в нашем проекте с переменными нашего окружения пайтон  

конкретно в нашем случае запускать
	"путь к исполняемому файлу блендера" --python scripts\script.py
