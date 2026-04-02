import flet as ft

def main(page: ft.Page):
    page.title = "Flet Test"
    page.add(ft.Text("Hello, Flet!"))

# 运行应用
ft.app(target=main)