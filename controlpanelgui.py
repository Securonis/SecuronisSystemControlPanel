#!/usr/bin/env python3
import tkinter as tk
from tkinter import font, ttk, messagebox
import psutil
import platform
import datetime
import socket
import subprocess
import re
import time
import os
import json
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
import queue
import signal
import sys
from PIL import Image, ImageTk


class LinuxSystemPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("Secuonis Linux System Control Panel v1.8")
        self.root.geometry("1200x750")
        self.root.configure(bg="#000000")
        
        # Cache for system information
        self._cache = {}
        self._cache_timeout = {}
        
        # Thread pool with limited workers
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.update_queue = queue.Queue()
        
        # Update intervals (in milliseconds)
        self.UPDATE_INTERVALS = {
            'cpu_ram': 2000,    # CPU/RAM update every 2 seconds
            'processes': 3000,   # Process list update every 3 seconds
            'disk': 10000,      # Disk info update every 10 seconds
            'network': 5000     # Network info update every 5 seconds
        }
        
        # Font settings
        self.title_font = font.Font(family="Ubuntu", size=12, weight="bold")
        self.bold_font = font.Font(family="Ubuntu", size=10, weight="bold")
        self.normal_font = font.Font(family="Ubuntu", size=9)
        
        # Stil settings
        self.style = ttk.Style()
        self.style.configure("Custom.TButton",
                           background="#121212",
                           foreground="#00ff00",
                           padding=5)
        
        # Configure scrollbar style
        self.style.layout("Vertical.TScrollbar", 
                         [('Vertical.Scrollbar.trough',
                           {'children': [('Vertical.Scrollbar.thumb', 
                                        {'expand': '1', 'sticky': 'nswe'})],
                            'sticky': 'ns'})])
        
        self.style.configure("Vertical.TScrollbar",
                           background="#006400",
                           darkcolor="#006400",
                           lightcolor="#006400",
                           troughcolor="#121212",
                           arrowcolor="#00ff00",
                           bordercolor="#006400",
                           relief="flat",
                           width=10)
        
        self.style.map("Vertical.TScrollbar",
                      background=[('pressed', '#008000'),
                                ('active', '#008000')],
                      darkcolor=[('pressed', '#008000'),
                               ('active', '#008000')],
                      lightcolor=[('pressed', '#008000'),
                                ('active', '#008000')])
        
        # main grid
        self.root.grid_columnconfigure(0, weight=0, minsize=220)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # menu
        self.sidebar = tk.Frame(root, bg="#121212", padx=15, pady=15)
        self.sidebar.grid(row=0, column=0, sticky="nswe")
        
        # Logo
        try:
            logo_image = Image.open("/usr/share/icons/securonis/newlogopng.png")
            logo_image = logo_image.resize((150, 150), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(self.sidebar, 
                                image=self.logo_photo,
                                bg="#121212")
            logo_label.pack(pady=(0, 30))
        except Exception as e:
            print(f"Logo error!: {e}")
            tk.Label(self.sidebar, 
                    text="SECURONIS SYSTEM PANEL", 
                    bg="#121212", 
                    fg="#00ff00",
                    font=self.title_font).pack(pady=(0, 30), anchor="w")
        
        # Menu buttons
        self.menu_items = [
            ("System Info", 0),
            ("Hardware Info", 1),
            ("Privacy Status", 2),
            ("Network Info", 3),
            ("Disk Info", 4),
            ("Processes", 5),
            ("Services", 6),
            ("Power Info", 7),
            ("Securonis", 8),
            ("About", 9)
        ]

        
        for text, index in self.menu_items:
            self.create_menu_button(text, index)
        
        # Create main scrollable area
        self.main_container = tk.Frame(root, bg="#000000")
        self.main_container.grid(row=0, column=1, sticky="nswe")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self.main_container, bg="#000000", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.main_container, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar")
        
        # Configure canvas
        self.main_area = tk.Frame(self.canvas, bg="#000000")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack scrollbar and canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create canvas window
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_area, anchor="nw", tags="self.main_area")
        
        # Configure canvas scrolling
        self.main_area.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.main_area.bind("<Enter>", self._bound_to_mousewheel)
        self.main_area.bind("<Leave>", self._unbound_to_mousewheel)
        
        # info bar
        self.bottom_bar = tk.Frame(root, bg="#121212", height=100)
        self.bottom_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.bottom_bar.grid_propagate(False)
        
        # CPU ram graphs
        self.create_usage_graphs()
        
        # show system info first 
        self.show_system_info()
        
        # updates
        self.start_periodic_updates()
        
        # signal
        signal.signal(signal.SIGINT, self.handle_signal)
        
        # window
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _bound_to_mousewheel(self, event, canvas=None):
        """Bind mousewheel when mouse enters the widget"""
        target_canvas = canvas if canvas else self.canvas
        if sys.platform.startswith('linux'):
            target_canvas.bind_all("<Button-4>", lambda e: self._on_mousewheel(e, target_canvas))
            target_canvas.bind_all("<Button-5>", lambda e: self._on_mousewheel(e, target_canvas))
        else:
            target_canvas.bind_all("<MouseWheel>", lambda e: self._on_mousewheel(e, target_canvas))

    def _unbound_to_mousewheel(self, event, canvas=None):
        """Unbind mousewheel when mouse leaves the widget"""
        target_canvas = canvas if canvas else self.canvas
        if sys.platform.startswith('linux'):
            target_canvas.unbind_all("<Button-4>")
            target_canvas.unbind_all("<Button-5>")
        else:
            target_canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event, canvas):
        """Handle mouse wheel scrolling for any canvas"""
        if hasattr(event, 'num'):  # Linux
            if event.num == 5:  # scroll down
                canvas.yview_scroll(1, "units")
            elif event.num == 4:  # scroll up
                canvas.yview_scroll(-1, "units")
        elif hasattr(event, 'delta'):  # Windows
            if event.delta < 0:  # scroll down
                canvas.yview_scroll(1, "units")
            else:  # scroll up
                canvas.yview_scroll(-1, "units")

    def on_frame_configure(self, event=None):
        """Reset the scroll region to encompass the inner frame"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Ensure the frame width matches the canvas width
        self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())

    def on_canvas_configure(self, event):
        """When the canvas is resized, resize the inner frame to match"""
        width = event.width
        self.canvas.itemconfig(self.canvas_window, width=width)
        # Update scroll region after canvas resize
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def create_usage_graphs(self):
        # CPU Graph
        cpu_frame = tk.Frame(self.bottom_bar, bg="#121212")
        cpu_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(cpu_frame,
                text="CPU Usage:",
                bg="#121212",
                fg="#00ff00",
                font=self.bold_font).pack(anchor="w")
        
        self.cpu_canvas = tk.Canvas(cpu_frame, height=30, bg="#121212", highlightthickness=0)
        self.cpu_canvas.pack(fill="x", pady=2)
        
        self.cpu_label = tk.Label(cpu_frame,
                                text="0%",
                                bg="#121212",
                                fg="#00ff00")
        self.cpu_label.pack(anchor="w")
        
        # RAM Graph
        ram_frame = tk.Frame(self.bottom_bar, bg="#121212")
        ram_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(ram_frame,
                text="RAM Usage:",
                bg="#121212",
                fg="#00ff00",
                font=self.bold_font).pack(anchor="w")
        
        self.ram_canvas = tk.Canvas(ram_frame, height=30, bg="#121212", highlightthickness=0)
        self.ram_canvas.pack(fill="x", pady=2)
        
        self.ram_label = tk.Label(ram_frame,
                                text="0%",
                                bg="#121212",
                                fg="#00ff00")
        self.ram_label.pack(anchor="w")

    def update_usage_graphs(self):
        try:
            if not hasattr(self, 'cpu_canvas') or not self.cpu_canvas.winfo_exists():
                return

            # Get CPU and RAM usage together to reduce system calls
            cpu_percent = psutil.cpu_percent(interval=None)  # Non-blocking call
            mem = psutil.virtual_memory()

            # Update CPU graph
            width = self.cpu_canvas.winfo_width()
            if width > 1:
                self.cpu_canvas.delete("all")
                self.cpu_canvas.create_rectangle(0, 0, (cpu_percent/100)*width, 30, fill="#006400", outline="")
                self.cpu_label.config(text=f"{cpu_percent:.1f}%")

            # Update RAM graph
            width = self.ram_canvas.winfo_width()
            if width > 1:
                self.ram_canvas.delete("all")
                self.ram_canvas.create_rectangle(0, 0, (mem.percent/100)*width, 30, fill="#006400", outline="")
                self.ram_label.config(text=f"{mem.percent:.1f}%")

            self.root.after(self.UPDATE_INTERVALS['cpu_ram'], self.update_usage_graphs)
        except Exception as e:
            print(f"Error updating graphs: {e}")

    def show_system_info(self):
        # Clear existing content
        for widget in self.main_area.winfo_children():
            widget.destroy()
            
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="SYSTEM INFORMATION", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        info_frame = tk.Frame(content, bg="#000000")
        info_frame.pack(fill="x")
        
        system_info = self.get_system_info()
        
        # system infos
        categories = {
            "System": ["Hostname", "OS", "Kernel", "Uptime", "Last Boot", "System Time", "Timezone"],
            "Hardware": ["CPU", "RAM", "Swap", "Temperature", "Load Avg", "Battery"],
            "Environment": ["Desktop Environment", "Display Manager", "Shell", "System Language"]
        }
        
        row = 0
        for category, items in categories.items():
            # catagori items
            tk.Label(info_frame, 
                    text=f"\n{category}:", 
                    bg="#000000", 
                    fg="#00ff00",
                    font=self.bold_font).grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 5))
            row += 1
            
            # catagories 
            for item in items:
                if item in system_info:
                    tk.Label(info_frame, 
                            text=f"{item}:", 
                            bg="#000000", 
                            fg="#00ff00",
                            font=self.bold_font, 
                            width=20, 
                            anchor="w").grid(row=row, column=0, sticky="w", pady=2)
                    tk.Label(info_frame, 
                            text=system_info[item], 
                            bg="#000000",
                            fg="#00ff00").grid(row=row, column=1, sticky="w", padx=10, pady=2)
                    row += 1

    def show_system_monitor(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="SYSTEM MONITOR", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        # Graphs
        graph_frame = tk.Frame(content, bg="#000000")
        graph_frame.pack(fill="both", expand=True, pady=10)
        
        # CPU Grafiği
        cpu_frame = tk.Frame(graph_frame, bg="#000000")
        cpu_frame.pack(fill="x", pady=5)
        tk.Label(cpu_frame, text="CPU Usage:", bg="#000000", fg="#00ff00", font=self.bold_font).pack(anchor="w")
        self.monitor_cpu_canvas = tk.Canvas(cpu_frame, height=100, bg="#121212", highlightthickness=0)
        self.monitor_cpu_canvas.pack(fill="x", pady=2)
        self.monitor_cpu_label = tk.Label(cpu_frame, text="0%", bg="#000000", fg="#00ff00")
        self.monitor_cpu_label.pack(anchor="w")
        
        # RAM Graph
        ram_frame = tk.Frame(graph_frame, bg="#000000")
        ram_frame.pack(fill="x", pady=5)
        tk.Label(ram_frame, text="RAM Usage:", bg="#000000", fg="#00ff00", font=self.bold_font).pack(anchor="w")
        self.monitor_ram_canvas = tk.Canvas(ram_frame, height=100, bg="#121212", highlightthickness=0)
        self.monitor_ram_canvas.pack(fill="x", pady=2)
        self.monitor_ram_label = tk.Label(ram_frame, text="0%", bg="#000000", fg="#00ff00")
        self.monitor_ram_label.pack(anchor="w")
        
        # Disk Graph
        disk_frame = tk.Frame(graph_frame, bg="#000000")
        disk_frame.pack(fill="x", pady=5)
        tk.Label(disk_frame, text="Disk Usage:", bg="#000000", fg="#00ff00", font=self.bold_font).pack(anchor="w")
        self.monitor_disk_canvas = tk.Canvas(disk_frame, height=100, bg="#121212", highlightthickness=0)
        self.monitor_disk_canvas.pack(fill="x", pady=2)
        self.monitor_disk_label = tk.Label(disk_frame, text="0%", bg="#000000", fg="#00ff00")
        self.monitor_disk_label.pack(anchor="w")
        
        # update graphics
        def update_graphs():
            try:
                if not content.winfo_exists():
                    return
                    
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.5)
                if hasattr(self, 'monitor_cpu_canvas') and self.monitor_cpu_canvas.winfo_exists():
                    self.monitor_cpu_canvas.delete("all")
                    width = self.monitor_cpu_canvas.winfo_width()
                    if width > 1:
                        self.monitor_cpu_canvas.create_rectangle(0, 0, (cpu_percent/100)*width, 100, fill="#006400", outline="")
                        self.monitor_cpu_label.config(text=f"{cpu_percent:.1f}%")
                
                # RAM usage
                mem = psutil.virtual_memory()
                if hasattr(self, 'monitor_ram_canvas') and self.monitor_ram_canvas.winfo_exists():
                    self.monitor_ram_canvas.delete("all")
                    width = self.monitor_ram_canvas.winfo_width()
                    if width > 1:
                        self.monitor_ram_canvas.create_rectangle(0, 0, (mem.percent/100)*width, 100, fill="#006400", outline="")
                        self.monitor_ram_label.config(text=f"{mem.percent:.1f}%")
                
                # Disk usage
                disk = psutil.disk_usage('/')
                if hasattr(self, 'monitor_disk_canvas') and self.monitor_disk_canvas.winfo_exists():
                    self.monitor_disk_canvas.delete("all")
                    width = self.monitor_disk_canvas.winfo_width()
                    if width > 1:
                        self.monitor_disk_canvas.create_rectangle(0, 0, (disk.percent/100)*width, 100, fill="#006400", outline="")
                        self.monitor_disk_label.config(text=f"{disk.percent:.1f}%")
                
                # update after 1 sec
                self.root.after(1000, update_graphs)
            except Exception as e:
                print(f"Error updating graphs: {e}")
        
        update_graphs()

    def handle_signal(self, signum, frame):
        """get the signals"""
        print("Received signal to close application")
        self.cleanup()
        sys.exit(0)

    def on_closing(self):
        """clean after shutdown"""
        print("Window closing, cleaning up...")
        self.cleanup()
        self.root.destroy()

    def cleanup(self):
        """Clean sources"""
        try:
            self.executor.shutdown(wait=False)
            print("Thread pool shutdown completed")
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def start_periodic_updates(self):
        """periodic updates"""
        def update():
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.5)
                if hasattr(self, 'cpu_canvas') and self.cpu_canvas.winfo_exists():
                    self.cpu_canvas.delete("all")
                    width = self.cpu_canvas.winfo_width()
                    if width > 1:
                        self.cpu_canvas.create_rectangle(0, 0, (cpu_percent/100)*width, 30, fill="#006400", outline="")
                        self.cpu_label.config(text=f"{cpu_percent:.1f}%")
                
                # RAM usage
                mem = psutil.virtual_memory()
                if hasattr(self, 'ram_canvas') and self.ram_canvas.winfo_exists():
                    self.ram_canvas.delete("all")
                    width = self.ram_canvas.winfo_width()
                    if width > 1:
                        self.ram_canvas.create_rectangle(0, 0, (mem.percent/100)*width, 30, fill="#006400", outline="")
                        self.ram_label.config(text=f"{mem.percent:.1f}%")
                
                # update after 1sec
                self.root.after(1000, update)
            except Exception as e:
                print(f"Error updating graphs: {e}")
        
        update()

    def update_status(self):
        """update status"""
        try:
            cpu_percent = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            uptime = self.get_uptime()
            
            self.cpu_label.config(text=f"{cpu_percent}%")
            self.ram_label.config(text=f"{mem.percent}%")
            
            self.cpu_canvas.delete("all")
            self.cpu_canvas.create_rectangle(0, 0, cpu_percent*2, 30, fill="#006400", outline="")
            
            self.ram_canvas.delete("all")
            self.ram_canvas.create_rectangle(0, 0, mem.percent*2, 30, fill="#006400", outline="")
            
            self.root.after(1000, self.update_status)
        except Exception as e:
            print(f"Error updating status: {e}")

    def get_uptime(self) -> str:
        """System work time"""
        try:
            uptime = time.time() - psutil.boot_time()
            days = int(uptime // (24 * 3600))
            hours = int((uptime % (24 * 3600)) // 3600)
            minutes = int((uptime % 3600) // 60)
            return f"{days}d {hours}h {minutes}m"
        except:
            return "N/A"

    def create_menu_button(self, text: str, index: int):
        """menu button"""
        btn = ttk.Button(self.sidebar,
                       text=text,
                       style="Custom.TButton",
                       command=lambda: self.switch_tab(index))
        btn.pack(fill="x", pady=3)

    def switch_tab(self, index: int):
        """change tabs"""
        try:
            for widget in self.main_area.winfo_children():
                widget.destroy()
            
            if index == 0:
                self.show_system_info()
            elif index == 1:
                self.show_hardware_info()
            elif index == 2:
                self.show_privacy_status()
            elif index == 3:
                self.show_network_info()
            elif index == 4:
                self.show_disk_info()
            elif index == 5:
                self.show_system_monitor()
            elif index == 6:
                self.show_services()
            elif index == 7:
                self.show_power_info()
            elif index == 8:
                self.show_securonis_info()
            elif index == 9:
                self.show_about()
            else:
                self.show_system_info()
        except Exception as e:
            print(f"Error switching tab: {e}")
            messagebox.showerror("Error", f"Failed to switch tab: {str(e)}")

    def show_about(self):
        """Show About tab with application information."""
        # Clear the main area
        for widget in self.main_area.winfo_children():
            widget.destroy()

        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)

        tk.Label(content, 
                 text="ABOUT THIS PANEL", 
                 font=self.title_font,
                 bg="#000000",
                 fg="#00ff00").pack(anchor="w", pady=(0, 20))

        about_text = (
            "Secuonis Linux System Control Panel\n\n"
            "Version: 1.8\n"
            "Developer: root0emir\n\n"
            "This control panel provides detailed system information, "
            "hardware monitoring, privacy and security status, and more.\n\n"
            "Features:\n"
            "- System and hardware information\n"
            "- Privacy and security checks\n"
            "- Network and disk monitoring\n"
            "- Process and service management\n"
            "- Power and system logs\n\n"
        )

        tk.Label(content, 
                 text=about_text, 
                 font=self.normal_font,
                 bg="#000000",
                 fg="#00ff00",
                 justify="left",
                 anchor="w").pack(anchor="w", pady=(10, 0))

    def get_system_info(self):
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return { 
            "Hostname": socket.gethostname(),
            "OS": self.get_os_info(),
            "Kernel": platform.version(),
            "Uptime": str(datetime.timedelta(seconds=int(time.time() - psutil.boot_time())))[:-7],
            "CPU": f"{psutil.cpu_percent()}% ({psutil.cpu_count()} cores @ {psutil.cpu_freq().current:.0f}MHz)",
            "RAM": f"{mem.used/1024/1024:.1f}MB / {mem.total/1024/1024:.1f}MB ({mem.percent}%)",
            "Swap": f"{swap.used/1024/1024:.1f}MB / {swap.total/1024/1024:.1f}MB",
            "Temperature": self.get_cpu_temp(),
            "Load Avg": self.get_load_avg(),
            "Battery": self.get_battery_info(),
            "Last Boot": datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
            "System Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Timezone": self.get_timezone(),
            "Desktop Environment": self.get_desktop_environment(),
            "Display Manager": self.get_display_manager(),
            "Shell": os.environ.get('SHELL', 'N/A'),
            "System Language": self.get_system_language()
        }

    def get_os_info(self):
        try:
            with open('/etc/os-release', 'r') as f:
                lines = f.readlines()
                os_info = {}
                for line in lines:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os_info[key] = value.strip('"')
                return f"{os_info.get('NAME', 'Unknown')} {os_info.get('VERSION', '')} ({os_info.get('ID', 'Unknown')})"
        except:
            return f"{platform.system()} {platform.release()}"

    def get_timezone(self):
        try:
            return subprocess.check_output(['timedatectl', 'show', '--property=Timezone']).decode().strip().split('=')[1]
        except:
            return "N/A"

    def get_desktop_environment(self):
        try:
            return os.environ.get('XDG_CURRENT_DESKTOP', 'N/A')
        except:
            return "N/A"

    def get_display_manager(self):
        try:
            return subprocess.check_output(['systemctl', 'list-units', '--type=service', '--state=running', 'display-manager.service']).decode()
        except:
            return "N/A"

    def get_system_language(self):
        try:
            return os.environ.get('LANG', 'N/A')
        except:
            return "N/A"

    def get_cpu_temp(self):
        try:
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                return f"{temps['coretemp'][0].current}°C"
            elif 'k10temp' in temps:
                return f"{temps['k10temp'][0].current}°C"
            elif 'acpitz' in temps:
                return f"{temps['acpitz'][0].current}°C"
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return f"{int(f.read()) / 1000}°C"
        except:
            return "N/A"

    def get_load_avg(self):
        try:
            with open("/proc/loadavg", "r") as f:
                load = f.read().split()[:3]
            return ", ".join(load)
        except:
            return "N/A"

    def get_battery_info(self):
        try:
            bat = psutil.sensors_battery()
            if bat:
                return f"{bat.percent}% ({'Charging' if bat.power_plugged else 'Discharging'})"
            return "No Battery"
        except:
            return "N/A"

    def show_hardware_info(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="HARDWARE INFORMATION", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        # CPU Details
        cpu_frame = tk.Frame(content, bg="#000000")
        cpu_frame.pack(fill="x", pady=10)
        
        tk.Label(cpu_frame,
                text="CPU Details:",
                bg="#000000",
                fg="#00ff00",
                font=self.bold_font).pack(anchor="w")
        
        cpu_info = self.get_cpu_details()
        for key, value in cpu_info.items():
            frame = tk.Frame(cpu_frame, bg="#000000")
            frame.pack(fill="x", pady=2)
            tk.Label(frame,
                    text=f"{key}:",
                    bg="#000000",
                    fg="#00ff00",
                    width=20,
                    anchor="w").pack(side="left")
            tk.Label(frame,
                    text=value,
                    bg="#000000",
                    fg="#00ff00").pack(side="left", padx=10)
        
        # GPU Details
        gpu_frame = tk.Frame(content, bg="#000000")
        gpu_frame.pack(fill="x", pady=10)
        
        tk.Label(gpu_frame,
                text="GPU Details:",
                bg="#000000",
                fg="#00ff00",
                font=self.bold_font).pack(anchor="w")
        
        gpu_info = self.get_gpu_details()
        for key, value in gpu_info.items():
            frame = tk.Frame(gpu_frame, bg="#000000")
            frame.pack(fill="x", pady=2)
            tk.Label(frame,
                    text=f"{key}:",
                    bg="#000000",
                    fg="#00ff00",
                    width=20,
                    anchor="w").pack(side="left")
            tk.Label(frame,
                    text=value,
                    bg="#000000",
                    fg="#00ff00").pack(side="left", padx=10)
        
        # RAM details
        ram_frame = tk.Frame(content, bg="#000000")
        ram_frame.pack(fill="x", pady=10)
        
        tk.Label(ram_frame,
                text="RAM Details:",
                bg="#000000",
                fg="#00ff00",
                font=self.bold_font).pack(anchor="w")
        
        ram_info = self.get_ram_details()
        for key, value in ram_info.items():
            frame = tk.Frame(ram_frame, bg="#000000")
            frame.pack(fill="x", pady=2)
            tk.Label(frame,
                    text=f"{key}:",
                    bg="#000000",
                    fg="#00ff00",
                    width=20,
                    anchor="w").pack(side="left")
            tk.Label(frame,
                    text=value,
                    bg="#000000",
                    fg="#00ff00").pack(side="left", padx=10)

    def get_cpu_details(self):
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpu_info = {}
                for line in f:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        cpu_info[key.strip()] = value.strip()
                
                return {
                    "Model": cpu_info.get('model name', 'N/A'),
                    "Vendor": cpu_info.get('vendor_id', 'N/A'),
                    "Cores": f"{psutil.cpu_count()} ({psutil.cpu_count(logical=False)} physical)",
                    "Thread Count": str(psutil.cpu_count(logical=True)),
                    "Cache Sizes": self.get_cpu_cache_sizes(),
                    "Max Speed": f"{psutil.cpu_freq().max:.0f}MHz",
                    "Current Speed": f"{psutil.cpu_freq().current:.0f}MHz",
                    "Min Speed": f"{psutil.cpu_freq().min:.0f}MHz"
                }
        except:
            return {"Error": "Could not fetch CPU details"}

    def get_cpu_cache_sizes(self):
        try:
            with open('/sys/devices/system/cpu/cpu0/cache/index0/size', 'r') as f:
                l1 = f.read().strip()
            with open('/sys/devices/system/cpu/cpu0/cache/index1/size', 'r') as f:
                l2 = f.read().strip()
            with open('/sys/devices/system/cpu/cpu0/cache/index2/size', 'r') as f:
                l3 = f.read().strip()
            return f"L1: {l1}, L2: {l2}, L3: {l3}"
        except:
            return "N/A"

    def get_gpu_details(self):
        try:
            # NVIDIA GPU
            nvidia = subprocess.check_output(['nvidia-smi', '--query-gpu=gpu_name,memory.total,memory.used,memory.free', '--format=csv,noheader']).decode()
            if nvidia:
                name, total, used, free = nvidia.strip().split(',')
                return {
                    "GPU": name,
                    "Total Memory": f"{total.strip()}",
                    "Used Memory": f"{used.strip()}",
                    "Free Memory": f"{free.strip()}"
                }
            
            # Intel/AMD GPU
            with open('/sys/kernel/debug/dri/0/i915_frequency_info', 'r') as f:
                gpu_info = f.read()
                return {
                    "GPU": "Intel/AMD Integrated Graphics",
                    "Frequency Info": gpu_info
                }
        except:
            return {"GPU": "N/A"}

    def get_ram_details(self):
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # RAM hızını kontrol et
            ram_speed = "N/A"
            try:
                with open('/sys/devices/system/memory/memory0/device/speed', 'r') as f:
                    ram_speed = f"{f.read().strip()} MHz"
            except:
                pass
            
            return {
                "Total RAM": f"{mem.total/1024/1024/1024:.1f} GB",
                "Available RAM": f"{mem.available/1024/1024/1024:.1f} GB",
                "Used RAM": f"{mem.used/1024/1024/1024:.1f} GB",
                "RAM Usage": f"{mem.percent}%",
                "RAM Speed": ram_speed,
                "Total Swap": f"{swap.total/1024/1024/1024:.1f} GB",
                "Used Swap": f"{swap.used/1024/1024/1024:.1f} GB",
                "Swap Usage": f"{swap.percent}%"
            }
        except:
            return {"Error": "Could not fetch RAM details"}

    def show_services(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="SYSTEM SERVICES", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        # service list
        services = self.get_system_services()
        
        for service in services:
            frame = tk.Frame(content, bg="#000000")
            frame.pack(fill="x", pady=2)
            
            tk.Label(frame,
                    text=f"{service['name']}:",
                    bg="#000000",
                    fg="#00ff00",
                    width=40,
                    anchor="w").pack(side="left")
            
            color = "#00ff00" if service['status'] == "active" else "#ff0000"
            tk.Label(frame,
                    text=service['status'],
                    bg="#000000",
                    fg=color).pack(side="left", padx=10)

    def get_system_services(self):
        try:
            output = subprocess.check_output(['systemctl', 'list-units', '--type=service', '--state=running']).decode()
            services = []
            for line in output.split('\n'):
                if 'running' in line:
                    name = line.split()[0]
                    status = 'active'
                    services.append({'name': name, 'status': status})
            return services
        except:
            return []

    def show_privacy_status(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="PRIVACY & SECURITY STATUS", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        loading_label = tk.Label(content, 
                               text="Loading security information...", 
                               bg="#000000",
                               fg="#00ff00")
        loading_label.pack(pady=20)
        
        # update sec info
        def update_security_info():
            try:
                if not content.winfo_exists():
                    return
                    
                security_info = {
                # sec
                "VPN Status": self.check_vpn(),
                "Tor Status": self.check_tor(),
                "DNS Status": self.check_dns(),
                "Public IP": self.get_public_ip(),
                
                # System Sec  
                "AppArmor": self.check_apparmor()
            }
                
                if loading_label.winfo_exists():
                    loading_label.destroy()
                
                # sec info
                for i, (key, value) in enumerate(security_info.items()):
                    if not content.winfo_exists():
                        return
                        
                    frame = tk.Frame(content, bg="#000000")
                    frame.pack(fill="x", pady=5)
                    
                    tk.Label(frame, 
                            text=f"{key}:", 
                            bg="#000000", 
                            fg="#00ff00",
                            font=self.bold_font, 
                            width=20, 
                            anchor="w").pack(side="left")
                    
                    color = "#00ff00" if value in ["Active", "Enabled", "Up to Date", "Protected", "Secure"] else "#ff0000" if value in ["Inactive", "Disabled", "Not Found", "Unprotected", "Insecure"] else "#ffff00"
                    tk.Label(frame, 
                            text=value, 
                            bg="#000000",
                            fg=color).pack(side="left", padx=10)
            except Exception as e:
                print(f"Error in update_security_info: {e}")
                if loading_label.winfo_exists():
                    loading_label.destroy()
                if content.winfo_exists():
                    tk.Label(content,
                            text="Error loading security information",
                            bg="#000000",
                            fg="#ff0000").pack(pady=20)
        
        # Asencron
        threading.Thread(target=update_security_info, daemon=True).start()

    def check_firewall(self):
        try:
            # UFW check
            ufw_status = subprocess.check_output(['ufw', 'status'], stderr=subprocess.PIPE, timeout=1).decode()
            if "Status: active" in ufw_status:
                return "Active"
            
            iptables_status = subprocess.check_output(['iptables', '-L'], stderr=subprocess.PIPE, timeout=1).decode()
            if "Chain INPUT" in iptables_status:
                return "Active (iptables)"
            
            return "Inactive"
        except:
            return "Not Found"

    def check_vpn(self):
        try:
            interfaces = psutil.net_if_stats()
            vpn_interfaces = ['tune0', 'tun0', 'tun1', 'wg0', 'ppp0', 'ppp1', 'ppp2']
            
            for interface in vpn_interfaces:
                if interface in interfaces and interfaces[interface].isup:
                    return "Active"
            
            return "Inactive"
        except:
            return "Not Found"

    def check_tor(self):
        try:
 
            tor_status = subprocess.check_output(['systemctl', 'is-active', 'tor'], stderr=subprocess.PIPE, timeout=1).decode()
            if "active" in tor_status:
               
                try:
                    import requests
                    session = requests.session()
                    session.proxies = {
                        'http': 'socks5h://127.0.0.1:9050',
                        'https': 'socks5h://127.0.0.1:9050'
                    }
                    response = session.get('https://check.torproject.org/api/ip', timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('IsTor', False):
                            return "Active (Verified)"
                        else:
                            return "Active (Not Verified)"
                except:
                    return "Active (Connection Failed)"
            return "Inactive"
        except:
            return "Not Found"

    def check_dns(self):
        try:
            with open('/etc/resolv.conf', 'r') as f:
                dns_content = f.read()
            
            dns_providers = {
                '1.1.1.1': 'Cloudflare',
                '1.0.0.1': 'Cloudflare',
                '8.8.8.8': 'Google',
                '8.8.4.4': 'Google',
                '9.9.9.9': 'Quad9',
                '149.112.112.112': 'Quad9',
                '208.67.222.222': 'OpenDNS',
                '208.67.220.220': 'OpenDNS',
                '94.140.14.14': 'AdGuard',
                '94.140.15.15': 'AdGuard',
                '77.88.8.8': 'Yandex.DNS',
                '77.88.8.1': 'Yandex.DNS',
                '76.76.19.19': 'Alternate DNS',
                '76.223.122.150': 'Alternate DNS',
                '185.228.168.9': 'CleanBrowsing',
                '185.228.169.9': 'CleanBrowsing',
                '64.6.64.6': 'Verisign',
                '64.6.65.6': 'Verisign',
                '156.154.70.1': 'Neustar',
                '156.154.71.1': 'Neustar',
                '8.26.56.26': 'Comodo Secure',
                '8.20.247.20': 'Comodo Secure'
            }
            
            for ip, provider in dns_providers.items():
                if ip in dns_content:
                    return f"Using {provider}"
            
            return "Using Default DNS"
        except:
            return "Unknown"

    def get_public_ip(self):
        try:
            response = requests.get('https://api.ipify.org?format=json', timeout=2)
            ip = response.json()['ip']
            return f"{ip}"
        except:
            return "Could not fetch IP"

    def show_network_info(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="NETWORK INFORMATION", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        loading_label = tk.Label(content, 
                               text="Loading network information...", 
                               bg="#000000",
                               fg="#00ff00")
        loading_label.pack(pady=20)
        
        # get net info
        def update_network_info():
            # get netw info
            net_info = self.get_network_info()
            
            loading_label.destroy()
            
            # catagories for netw inf
            categories = {
                "Basic Information": ["IP Address", "MAC Address", "Hostname", "Domain"],
                "Network Interfaces": ["Interfaces", "Active Interface", "Interface Speed", "MTU Size"],
                "Traffic Statistics": ["Download", "Upload", "Packets", "Errors", "Drops"],
                "Network Services": ["DNS Servers", "Default Gateway", "DHCP Status", "Proxy Status"],
                "Network Security": ["Firewall Rules", "Network Encryption", "VPN Status"]
            }
            
            row = 0
            for category, items in categories.items():
              
                tk.Label(content, 
                        text=f"\n{category}:", 
                        bg="#000000", 
                        fg="#00ff00",
                        font=self.bold_font).pack(anchor="w", pady=(10, 5))
                
               
                for item in items:
                    if item in net_info:
                        frame = tk.Frame(content, bg="#000000")
                        frame.pack(fill="x", pady=2)
                        
                        tk.Label(frame, 
                                text=f"{item}:", 
                                bg="#000000", 
                                fg="#00ff00",
                                font=self.bold_font, 
                                width=20, 
                                anchor="w").pack(side="left")
                        
                        tk.Label(frame, 
                                text=net_info[item], 
                                bg="#000000",
                                fg="#00ff00").pack(side="left", padx=10)
            
        
            self.create_network_graph(content)
        
      
        threading.Thread(target=update_network_info, daemon=True).start()

    def get_network_info(self):
        try:
            net = psutil.net_io_counters()
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            
           
            info = {
                "IP Address": self.get_ip_address(),
                "MAC Address": self.get_mac_address(),
                "Hostname": socket.gethostname(),
                "Domain": self.get_domain_name(),
                
              
                "Interfaces": self.get_interface_status(),
                "Active Interface": self.get_active_interface(),
                "Interface Speed": self.get_interface_speed(),
                "MTU Size": self.get_mtu_size(),
                
                
                "Download": f"{net.bytes_recv/1024/1024:.1f} MB",
                "Upload": f"{net.bytes_sent/1024/1024:.1f} MB",
                "Packets": f"↓{net.packets_recv} ↑{net.packets_sent}",
                "Errors": f"↓{net.errin} ↑{net.errout}",
                "Drops": f"↓{net.dropin} ↑{net.dropout}",
                
              
                "DNS Servers": self.get_dns_servers(),
                "Default Gateway": self.get_default_gateway(),
                "DHCP Status": self.get_dhcp_status(),
                "Proxy Status": self.get_proxy_status(),
                
        
                "Firewall Rules": self.get_firewall_rules(),
                "Network Encryption": self.get_network_encryption_status(),
                "VPN Status": self.get_vpn_status()
            }
            return info
        except Exception as e:
            print(f"Error getting network info: {e}")
            return {"Error": "Could not fetch network information"}

    def get_domain_name(self):
        try:
            return socket.getfqdn()
        except:
            return "N/A"

    def get_active_interface(self):
        try:
            for interface, stats in psutil.net_if_stats().items():
                if stats.isup:
                    return interface
            return "N/A"
        except:
            return "N/A"

    def get_interface_speed(self):
        try:
            active_interface = self.get_active_interface()
            if active_interface != "N/A":
                with open(f'/sys/class/net/{active_interface}/speed', 'r') as f:
                    return f"{f.read().strip()} Mbps"
            return "N/A"
        except:
            return "N/A"

    def get_mtu_size(self):
        try:
            active_interface = self.get_active_interface()
            if active_interface != "N/A":
                with open(f'/sys/class/net/{active_interface}/mtu', 'r') as f:
                    return f"{f.read().strip()} bytes"
            return "N/A"
        except:
            return "N/A"

    def get_dns_servers(self):
        try:
            with open('/etc/resolv.conf', 'r') as f:
                dns_servers = []
                for line in f:
                    if line.startswith('nameserver'):
                        dns_servers.append(line.split()[1])
                return ", ".join(dns_servers) if dns_servers else "N/A"
        except:
            return "N/A"

    def get_default_gateway(self):
        try:
            with open('/proc/net/route', 'r') as f:
                for line in f:
                    if line.split()[0] == 'default':
                        return line.split()[2]
            return "N/A"
        except:
            return "N/A"

    def get_dhcp_status(self):
        try:
            dhcp_status = subprocess.check_output(['systemctl', 'is-active', 'dhcpcd'], stderr=subprocess.PIPE, timeout=1).decode()
            return "Active" if "active" in dhcp_status else "Inactive"
        except:
            return "N/A"

    def get_proxy_status(self):
        try:
            proxy_env = os.environ.get('http_proxy') or os.environ.get('https_proxy')
            if proxy_env:
                return f"Enabled ({proxy_env})"
            return "Disabled"
        except:
            return "N/A"

    def get_firewall_rules(self):
        try:
            rules = subprocess.check_output(['iptables', '-L', '--line-numbers'], stderr=subprocess.PIPE, timeout=1).decode()
            return f"{len(rules.splitlines())} rules"
        except:
            return "N/A"

    def get_network_encryption_status(self):
        try:
            ssl_status = subprocess.check_output(['openssl', 'version'], stderr=subprocess.PIPE, timeout=1).decode()
            return "Enabled" if ssl_status else "Disabled"
        except:
            return "N/A"

    def get_vpn_status(self):
        try:
            interfaces = psutil.net_if_stats()
            vpn_interfaces = ['tun0', 'tun1', 'wg0', 'ppp0']
            for interface in vpn_interfaces:
                if interface in interfaces and interfaces[interface].isup:
                    return "Active"
            return "Inactive"
        except:
            return "N/A"

    def create_network_graph(self, parent):
        frame = tk.Frame(parent, bg="#000000")
        frame.pack(fill="x", pady=20)
        
        tk.Label(frame,
                text="Network Traffic:",
                bg="#000000",
                fg="#00ff00",
                font=self.bold_font).pack(anchor="w")
        
        canvas = tk.Canvas(frame, height=100, bg="#121212", highlightthickness=0)
        canvas.pack(fill="x", pady=5)
        
        net = psutil.net_io_counters()
        total_bytes = net.bytes_sent + net.bytes_recv
        
        canvas.create_rectangle(0, 0, 200, 100, fill="#121212", outline="")
        canvas.create_rectangle(0, 0, (net.bytes_sent/total_bytes)*200, 100, fill="#006400", outline="")
        canvas.create_rectangle(0, 50, 200, 100, fill="#121212", outline="")
        canvas.create_rectangle(0, 50, (net.bytes_recv/total_bytes)*200, 100, fill="#006400", outline="")
        
        tk.Label(frame,
                text=f"↑ {net.bytes_sent/1024/1024:.1f}MB  ↓ {net.bytes_recv/1024/1024:.1f}MB",
                bg="#000000",
                fg="#00ff00").pack(anchor="w")

    def show_system_logs(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="SYSTEM LOGS", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        log_files = {
            "System Log": "/var/log/syslog",
            "Authentication Log": "/var/log/auth.log",
            "Kernel Log": "/var/log/kern.log",
            "Boot Log": "/var/log/boot.log",
            "Application Log": "/var/log/applications.log"
        }
        
        for log_name, log_path in log_files.items():
            frame = tk.Frame(content, bg="#000000")
            frame.pack(fill="x", pady=5)
            
            tk.Label(frame,
                    text=f"{log_name}:",
                    bg="#000000",
                    fg="#00ff00",
                    font=self.bold_font,
                    width=20,
                    anchor="w").pack(side="left")
            
            try:
                if os.path.exists(log_path):
                    with open(log_path, 'r') as f:
                        lines = f.readlines()[-5:]
                        status = "Last 5 lines available"
                else:
                    status = "File not found"
            except:
                status = "Access denied"
            
            tk.Label(frame,
                    text=status,
                    bg="#000000",
                    fg="#00ff00").pack(side="left", padx=10)

    def show_power_info(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="POWER INFORMATION", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        # power info
        power_info = self.get_power_info()
        
        for key, value in power_info.items():
            frame = tk.Frame(content, bg="#000000")
            frame.pack(fill="x", pady=5)
            
            tk.Label(frame,
                    text=f"{key}:",
                    bg="#000000",
                    fg="#00ff00",
                    font=self.bold_font,
                    width=20,
                    anchor="w").pack(side="left")
            
            tk.Label(frame,
                    text=value,
                    bg="#000000",
                    fg="#00ff00").pack(side="left", padx=10)

    def get_power_info(self):
        try:
            battery = psutil.sensors_battery()
            power_info = {}
            
            if battery:
                power_info["Battery Status"] = "Charging" if battery.power_plugged else "Discharging"
                power_info["Battery Level"] = f"{battery.percent}%"
                power_info["Time Left"] = f"{battery.secsleft/60:.1f} minutes" if battery.secsleft != -2 else "Calculating..."
            
            # CPU frekans info
            cpu_freq = psutil.cpu_freq()
            power_info["CPU Frequency"] = f"{cpu_freq.current:.0f}MHz"
            power_info["CPU Min Frequency"] = f"{cpu_freq.min:.0f}MHz"
            power_info["CPU Max Frequency"] = f"{cpu_freq.max:.0f}MHz"
            
            # Power status
            try:
                with open('/sys/class/power_supply/BAT0/power_now', 'r') as f:
                    power_now = int(f.read()) / 1000000  # Convert to watts
                    power_info["Current Power Usage"] = f"{power_now:.1f}W"
            except:
                power_info["Current Power Usage"] = "N/A"
            
            return power_info
        except:
            return {"Error": "Could not fetch power information"}

    def check_kernel_hardening(self):
        try:
            # Kernel hardening check
            with open('/proc/sys/kernel/randomize_va_space', 'r') as f:
                aslr = f.read().strip()
            with open('/proc/sys/fs/protected_hardlinks', 'r') as f:
                hardlinks = f.read().strip()
            with open('/proc/sys/fs/protected_symlinks', 'r') as f:
                symlinks = f.read().strip()
            
            if aslr == "2" and hardlinks == "1" and symlinks == "1":
                return "Enabled"
            return "Partially Enabled"
        except:
            return "Not Found"

    def check_usb_protection(self):
        try:
            # USB sec settings
            usb_status = subprocess.check_output(['lsusb'], stderr=subprocess.PIPE, timeout=1).decode()
            if "USB" in usb_status:
                return "Active"
            return "Inactive"
        except:
            return "Not Found"

    def check_ssh_status(self):
        try:
            ssh_status = subprocess.check_output(['systemctl', 'is-active', 'ssh'], stderr=subprocess.PIPE, timeout=1).decode()
            if "active" in ssh_status:
                return "Active"
            return "Inactive"
        except:
            return "Not Found"

    def check_network_encryption(self):
        try:
            # SSL/TLS checking
            ssl_status = subprocess.check_output(['openssl', 'version'], stderr=subprocess.PIPE, timeout=1).decode()
            if ssl_status:
                return "Enabled"
            return "Disabled"
        except:
            return "Not Found"

    def check_dns_over_tls(self):
        try:
            # DNS-over-TLS cechking
            with open('/etc/systemd/resolved.conf', 'r') as f:
                if 'DNSOverTLS=yes' in f.read():
                    return "Enabled"
            return "Disabled"
        except:
            return "Not Found"

    def check_updates(self):
        try:
            # APT check
            apt_status = subprocess.check_output(['apt', 'list', '--upgradable'], stderr=subprocess.PIPE, timeout=1).decode()
            if "Listing..." in apt_status and "upgradable" in apt_status:
                return "Updates Available"
            return "Up to Date"
        except:
            return "Unknown"

    def check_antivirus(self):
        try:
            # ClamAV kontrolü
            clamav_status = subprocess.check_output(['systemctl', 'is-active', 'clamav-daemon'], stderr=subprocess.PIPE, timeout=1).decode()
            if "active" in clamav_status:
                return "Active (ClamAV)"
            return "Not Found"
        except:
            return "Not Found"

    def check_selinux(self):
        try:
            selinux_status = subprocess.check_output(['getenforce'], stderr=subprocess.PIPE, timeout=1).decode().strip()
            return selinux_status
        except:
            return "Not Found"

    def check_apparmor(self):
        try:
            apparmor_status = subprocess.check_output(['systemctl', 'status', 'apparmor'], stderr=subprocess.PIPE, timeout=1).decode()
            if "active (exited)" in apparmor_status or "active (running)" in apparmor_status:
                return "Active"
            elif "inactive" in apparmor_status or "failed" in apparmor_status:
                return "Inactive"
            return "Unknown"
        except:
            return "Not Found"

    def show_disk_info(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="DISK INFORMATION", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        # Create container frame
        container = tk.Frame(content, bg="#000000")
        container.pack(fill="both", expand=True)
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(container, bg="#000000", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", 
                                command=canvas.yview, 
                                style="Vertical.TScrollbar")
        
        # Create frame for disk info
        scrollable_frame = tk.Frame(canvas, bg="#000000")
        
        # Configure scrolling
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Create window in canvas
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configure mouse wheel scrolling
        scrollable_frame.bind("<Enter>", lambda e: self._bound_to_mousewheel(e, canvas))
        scrollable_frame.bind("<Leave>", lambda e: self._unbound_to_mousewheel(e, canvas))
        
        # Loading label
        loading_label = tk.Label(scrollable_frame, 
                               text="Loading disk information...", 
                               bg="#000000", 
                               fg="#00ff00")
        loading_label.pack(pady=20)
        
        def update_disk_info():
            try:
                if not scrollable_frame.winfo_exists():
                    return
                
                # Get disk info using cache
                disks = self.get_cached_data('disk_info', self.get_disk_info, timeout=10)
                
                if loading_label.winfo_exists():
                    loading_label.destroy()
                
                # Clear existing disk frames
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()
                
                # Create frames for each disk
                for disk in disks:
                    frame = tk.Frame(scrollable_frame, bg="#000000")
                    frame.pack(fill="x", pady=10, padx=5)
                    
                    tk.Label(frame, 
                            text=f"{disk['Mount']}:", 
                            bg="#000000", 
                            fg="#00ff00",
                            font=self.bold_font, 
                            width=20, 
                            anchor="w").pack(side="left")
                    
                    canvas_width = 200
                    disk_canvas = tk.Canvas(frame, height=20, width=canvas_width, 
                                         bg="#121212", highlightthickness=0)
                    disk_canvas.pack(side="left", padx=10)
                    
                    percent = float(disk['Used'].replace('%', ''))
                    bar_width = (percent / 100.0) * canvas_width
                    disk_canvas.create_rectangle(0, 0, bar_width, 20, fill="#006400", outline="")
                    
                    tk.Label(frame, 
                            text=f"{disk['Used']} of {disk['Size']} (Free: {disk['Free']})", 
                            bg="#000000",
                            fg="#00ff00").pack(side="left", padx=10)
                
                # Pack canvas and scrollbar
                canvas.pack(side="left", fill="both", expand=True)
                if len(disks) > 4:
                    scrollbar.pack(side="right", fill="y")
                
            except Exception as e:
                print(f"Error updating disk info: {e}")
                if loading_label.winfo_exists():
                    loading_label.destroy()
                if scrollable_frame.winfo_exists():
                    tk.Label(scrollable_frame, 
                            text=f"Error loading disk information: {str(e)}", 
                            bg="#000000", 
                            fg="#ff0000").pack(pady=20)
        
        # Initial update
        update_disk_info()
        
        # Schedule periodic updates
        self.root.after(self.UPDATE_INTERVALS['disk'], update_disk_info)

    def get_disk_info(self):
        try:
            partitions = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "Mount": part.mountpoint,
                        "Used": f"{usage.percent}%",
                        "Size": f"{usage.total/1024/1024/1024:.1f} GB",
                        "Free": f"{usage.free/1024/1024/1024:.1f} GB",
                        "Type": part.fstype
                    })
                except:
                    continue
            return partitions
        except:
            return []

    def get_ip_address(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except:
            return "N/A"

    def get_mac_address(self):
        try:
            mac = psutil.net_if_addrs()[list(psutil.net_if_addrs().keys())[0]][0].address
            return mac if mac.count(':') == 5 else "N/A"
        except:
            return "N/A"

    def get_interface_status(self):
        try:
            stats = psutil.net_if_stats()
            return "\n".join([f"{k}: {'Up' if v.isup else 'Down'}" for k, v in stats.items()])
        except:
            return "N/A"

    def show_processes(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="TOP PROCESSES", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        # Create scrollable frame for processes
        process_container = tk.Frame(content, bg="#000000")
        process_container.pack(fill="both", expand=True)
        
        process_canvas = tk.Canvas(process_container, bg="#000000", highlightthickness=0)
        process_scrollbar = ttk.Scrollbar(process_container, orient="vertical", 
                                        command=process_canvas.yview, 
                                        style="Vertical.TScrollbar")
        scrollable_frame = tk.Frame(process_canvas, bg="#000000")
        
        scrollable_frame.bind("<Configure>", 
            lambda e: process_canvas.configure(scrollregion=process_canvas.bbox("all")))
        
        process_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        process_canvas.configure(yscrollcommand=process_scrollbar.set)
        
        # Configure mouse wheel scrolling
        scrollable_frame.bind("<Enter>", lambda e: self._bound_to_mousewheel(e, process_canvas))
        scrollable_frame.bind("<Leave>", lambda e: self._unbound_to_mousewheel(e, process_canvas))
        
        # Headers frame
        headers_frame = tk.Frame(scrollable_frame, bg="#000000")
        headers_frame.pack(fill="x", pady=(0, 5))
        
        tk.Label(headers_frame,
                text="Process Name",
                bg="#000000",
                fg="#00ff00",
                font=self.bold_font,
                width=40,
                anchor="w").pack(side="left")
        
        tk.Label(headers_frame,
                text="CPU %",
                bg="#000000",
                fg="#00ff00",
                font=self.bold_font,
                width=10).pack(side="left", padx=10)
        
        tk.Label(headers_frame,
                text="Memory %",
                bg="#000000",
                fg="#00ff00",
                font=self.bold_font,
                width=10).pack(side="left", padx=10)
        
        tk.Label(headers_frame,
                text="Status",
                bg="#000000",
                fg="#00ff00",
                font=self.bold_font,
                width=10).pack(side="left", padx=10)
        
        def update_processes():
            try:
                if not scrollable_frame.winfo_exists():
                    return

                # Clear existing process frames except headers
                for widget in scrollable_frame.winfo_children():
                    if widget != headers_frame:
                        widget.destroy()

                # Get process info more efficiently
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                    try:
                        info = proc.info
                        if info['cpu_percent'] > 0.1:  # Only show processes using CPU
                            processes.append(info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Sort and limit to top 5 CPU using processes
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
                top_processes = processes[:5]

                for proc in top_processes:
                    if not scrollable_frame.winfo_exists():
                        return

                    frame = tk.Frame(scrollable_frame, bg="#000000")
                    frame.pack(fill="x", pady=2)

                    # Create all labels at once
                    labels = [
                        (proc['name'], 40, "w"),
                        (f"{proc['cpu_percent']:.1f}%", 10, "center"),
                        (f"{proc['memory_percent']:.1f}%", 10, "center"),
                        (proc['status'], 10, "center")
                    ]

                    for text, width, anchor in labels:
                        tk.Label(frame,
                                text=text,
                                bg="#000000",
                                fg="#00ff00",
                                width=width,
                                anchor=anchor).pack(side="left", padx=10)

                # Pack scrollbar and canvas
                process_canvas.pack(side="left", fill="both", expand=True)
                process_scrollbar.pack(side="right", fill="y")

                # Update after interval
                self.root.after(self.UPDATE_INTERVALS['processes'], update_processes)

            except Exception as e:
                print(f"Error updating processes: {e}")

        update_processes()

    def get_cached_data(self, key, fetch_func, timeout=5):
        """Get cached data or fetch new data if cache expired"""
        current_time = time.time()
        if key not in self._cache or current_time - self._cache_timeout.get(key, 0) > timeout:
            self._cache[key] = fetch_func()
            self._cache_timeout[key] = current_time
        return self._cache[key]

    def show_securonis_info(self):
        content = tk.Frame(self.main_area, bg="#000000")
        content.pack(fill="both", expand=True, padx=25, pady=25)
        
        tk.Label(content, 
                text="SECURONIS INFORMATION", 
                font=self.title_font,
                bg="#000000",
                fg="#00ff00").pack(anchor="w", pady=(0, 20))
        
        info_frame = tk.Frame(content, bg="#000000", padx=20, pady=20)
        info_frame.pack(fill="both", expand=True)
        
        securonis_info = {
            "System": "Securonis GNU/Linux",
            "Version": "4.0",
            "Release": "Rolling",
            "Based On": "Debian Trixie",
            "Codename": "Kagune",
            "Version Stage": "Beta",
            "Seconionis Version": "2.0",
            "Securonis Web Site": "securonis.github.io",
            "Developer": "root0emir",
            "Developer Mail": "root0emir@protonmail.com"
        }
        
        # Display the information in a clean format
        for key, value in securonis_info.items():
            row = tk.Frame(info_frame, bg="#000000")
            row.pack(fill="x", pady=8)
            
            tk.Label(row, 
                    text=f"{key}:", 
                    font=self.bold_font,
                    bg="#000000", 
                    fg="#00ff00",
                    width=20,
                    anchor="w").pack(side="left")
                    
            tk.Label(row, 
                    text=value, 
                    bg="#000000", 
                    fg="#00ff00",
                    anchor="w").pack(side="left", padx=10)

if __name__ == "__main__":
    root = tk.Tk()
    app = LinuxSystemPanel(root)
    root.mainloop()
