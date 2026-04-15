import tkinter as tk
from dotenv import load_dotenv
from ui.components import LoginWindow
from ui.main_window import AppMainWindow

load_dotenv()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    
    login = LoginWindow(root)
    root.wait_window(login.top)
    
    if login.result:
        root.deiconify()
        app = AppMainWindow(root, current_admin=login.admin)
        root.mainloop()
    else:
        root.destroy()