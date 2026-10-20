## Что это
Данная библиотека служит для быстрого написания консольного управления в приложении

## Быстрый старт
```python
from mypyconsole import MyPyConsole

console = MyPyConsole()

def Config():
	console.name = "my-console-name"
	console.AddItem("aaa", func1, "some function") # "aaa" - cmd; func1 - function; "some function" - description
#end define

def func1(args):
	print("qwerty")
#end define


###
### Start of the program
###

if __name__ == "__main__":
	Config()
	console.Run()
#end if
```
