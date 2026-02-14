import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import threading
import time
import psutil
import pandas as pd
from datetime import datetime
from data_collection import ProcessDataCollector
from data_processing import process_data, terminate_process, get_process_details

# Performance optimization: Pre-calculate CPU percent in background
class CPUMonitor:
    """Non-blocking CPU monitor that updates in background"""
    def __init__(self):
        self._cpu_percent = 0.0
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
    
    def _monitor_loop(self):
        while self._running:
            # This blocks for 1 second, but in a background thread
            self._cpu_percent = psutil.cpu_percent(interval=1)
    
    def get_cpu_percent(self):
        return self._cpu_percent
    
    def stop(self):
        self._running = False

class ProcessMonitorDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time Process Monitoring Dashboard")
        self.root.geometry("1200x700")
        self.root.configure(bg="#0a0a0f")
        
        # Initialize non-blocking CPU monitor
        self.cpu_monitor = CPUMonitor()

        # Enhanced Style configuration with modern look
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", 
            font=("Segoe UI", 10, "bold"), 
            background="#6366f1", 
            foreground="white",
            padding=(12, 6),
            borderwidth=0)
        style.map("TButton", 
            background=[("active", "#818cf8"), ("pressed", "#4f46e5")],
            foreground=[("active", "white")])
        style.configure("Treeview", 
            background="#16161e", 
            foreground="#e2e8f0", 
            fieldbackground="#16161e", 
            font=("Segoe UI", 10),
            rowheight=28)
        style.configure("Treeview.Heading", 
            background="#3730a3", 
            foreground="white", 
            font=("Segoe UI", 11, "bold"),
            padding=(8, 4))
        style.map("Treeview",
            background=[("selected", "#4f46e5")],
            foreground=[("selected", "white")])

        # Modern gradient-style header
        header_frame = tk.Frame(root, bg="#3730a3", height=60)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        header = tk.Label(header_frame, 
            text="⚡ Real-Time Process Monitor", 
            font=("Segoe UI", 20, "bold"), 
            bg="#3730a3", 
            fg="white")
        header.pack(pady=12)

        # Modern system summary cards
        summary_frame = tk.Frame(root, bg="#0a0a0f")
        summary_frame.pack(fill="x", padx=15, pady=10)
        
        # CPU Card
        cpu_card = tk.Frame(summary_frame, bg="#1e1b4b", highlightbackground="#6366f1", highlightthickness=1)
        cpu_card.pack(side="left", padx=5, pady=5, ipadx=20, ipady=8)
        tk.Label(cpu_card, text="🖥️ CPU", font=("Segoe UI", 9), bg="#1e1b4b", fg="#a5b4fc").pack(anchor="w")
        self.cpu_label = tk.Label(cpu_card, text="0%", font=("Segoe UI", 18, "bold"), bg="#1e1b4b", fg="#c7d2fe")
        self.cpu_label.pack(anchor="w")
        
        # Memory Card
        mem_card = tk.Frame(summary_frame, bg="#1e1b4b", highlightbackground="#6366f1", highlightthickness=1)
        mem_card.pack(side="left", padx=5, pady=5, ipadx=20, ipady=8)
        tk.Label(mem_card, text="💾 Memory", font=("Segoe UI", 9), bg="#1e1b4b", fg="#a5b4fc").pack(anchor="w")
        self.memory_label = tk.Label(mem_card, text="0 GB / 0 GB (0%)", font=("Segoe UI", 14, "bold"), bg="#1e1b4b", fg="#c7d2fe")
        self.memory_label.pack(anchor="w")
        
        # Process Count Card
        proc_card = tk.Frame(summary_frame, bg="#1e1b4b", highlightbackground="#6366f1", highlightthickness=1)
        proc_card.pack(side="left", padx=5, pady=5, ipadx=20, ipady=8)
        tk.Label(proc_card, text="📊 Processes", font=("Segoe UI", 9), bg="#1e1b4b", fg="#a5b4fc").pack(anchor="w")
        self.process_count_label = tk.Label(proc_card, text="0", font=("Segoe UI", 18, "bold"), bg="#1e1b4b", fg="#c7d2fe")
        self.process_count_label.pack(anchor="w")

        # Modern search bar
        search_frame = tk.Frame(root, bg="#0a0a0f")
        search_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(search_frame, text="🔍", font=("Segoe UI", 12), bg="#0a0a0f", fg="#a5b4fc").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.debounce_search)
        self.search_entry = tk.Entry(search_frame, 
            textvariable=self.search_var, 
            font=("Segoe UI", 11), 
            bg="#1e1b4b", 
            fg="#e2e8f0", 
            insertbackground="#a5b4fc",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#4f46e5",
            highlightcolor="#818cf8")
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True, ipady=6)
        ttk.Button(search_frame, text="✖ Clear", command=self.clear_search).pack(side="left", padx=5)

        # Process table with improved styling
        table_frame = tk.Frame(root, bg="#0a0a0f", highlightbackground="#4f46e5", highlightthickness=1)
        table_frame.pack(fill="both", expand=True, padx=15, pady=8)
        self.tree = ttk.Treeview(table_frame, columns=('PID', 'Name', 'State', 'CPU (%)', 'Memory (MB)', 'Duration'), show='headings', height=12)
        
        # Column configuration with better widths
        col_widths = {'PID': 80, 'Name': 200, 'State': 100, 'CPU (%)': 100, 'Memory (MB)': 120, 'Duration': 120}
        for col in self.tree['columns']:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 120), anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        
        # Custom scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.focus_set()
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # Pagination controls
        pagination_frame = tk.Frame(root, bg="#0a0a0f")
        pagination_frame.pack(fill="x", padx=15, pady=5)
        self.page_var = tk.StringVar(value="Page 1")
        tk.Label(pagination_frame, textvariable=self.page_var, font=("Segoe UI", 10), bg="#0a0a0f", fg="#a5b4fc").pack(side="left", padx=5)
        ttk.Button(pagination_frame, text="◀ Prev", command=self.prev_page).pack(side="left", padx=3)
        ttk.Button(pagination_frame, text="Next ▶", command=self.next_page).pack(side="left", padx=3)

        # Action buttons with icons
        button_frame = tk.Frame(root, bg="#0a0a0f")
        button_frame.pack(fill="x", padx=15, pady=5)
        ttk.Button(button_frame, text="⛔ Terminate", command=self.terminate_selected).pack(side="left", padx=3)
        ttk.Button(button_frame, text="ℹ️ Details", command=self.show_details).pack(side="left", padx=3)
        ttk.Button(button_frame, text="🔄 Refresh", command=self.refresh_now).pack(side="left", padx=3)
        ttk.Button(button_frame, text="✖ Deselect", command=self.deselect_process).pack(side="left", padx=3)

        # Optimized graphs with persistent line objects for better performance
        graph_frame = tk.Frame(root, bg="#0a0a0f", highlightbackground="#4f46e5", highlightthickness=1)
        graph_frame.pack(fill="x", padx=15, pady=8)
        
        # Create figure with dark theme
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(10, 3.5))
        self.fig.patch.set_facecolor("#0a0a0f")
        self.fig.subplots_adjust(left=0.08, right=0.95, bottom=0.15, top=0.85, wspace=0.25)
        
        # Style axes
        for ax in [self.ax1, self.ax2]:
            ax.set_facecolor("#16161e")
            ax.tick_params(colors="#a5b4fc", labelsize=9)
            ax.spines['bottom'].set_color('#4f46e5')
            ax.spines['top'].set_color('#4f46e5')
            ax.spines['left'].set_color('#4f46e5')
            ax.spines['right'].set_color('#4f46e5')
            ax.grid(True, color="#3730a3", linestyle="--", alpha=0.4)
            ax.set_ylim(0, 100)
        
        self.ax1.set_title("CPU Usage (%)", color="#c7d2fe", fontsize=11, fontweight='bold')
        self.ax2.set_title("Memory Usage (%)", color="#c7d2fe", fontsize=11, fontweight='bold')
        
        # Pre-create line objects for efficient updates (avoid full redraws)
        self.cpu_data = [0] * 60
        self.memory_data = [0] * 60
        self.cpu_line, = self.ax1.plot(self.cpu_data, color="#818cf8", linewidth=2)
        self.mem_line, = self.ax2.plot(self.memory_data, color="#fbbf24", linewidth=2)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack()
        self.canvas.draw()  # Initial draw
        
        # Cache background for blitting optimization
        self.graph_bg = None

        # Modern status bar
        status_frame = tk.Frame(root, bg="#1e1b4b")
        status_frame.pack(fill="x", padx=15, pady=(5, 10))
        self.status_bar = tk.Label(status_frame, text="⏱️ Last Updated: Not yet updated", font=("Segoe UI", 10), bg="#1e1b4b", fg="#a5b4fc", anchor="w")
        self.status_bar.pack(fill="x", padx=10, pady=5)

        # Initialize process data
        self.collector = ProcessDataCollector()
        self.all_processes = pd.DataFrame()
        self.filtered_processes = pd.DataFrame()
        self.search_after_id = None
        self.last_graph_update = 0
        self.current_page = 0
        self.processes_per_page = 50
        self.last_update_time = 0
        self.update_interval = 3  # Increased from 2 to 3 seconds for better performance
        self.selected_pid = None

        # Start real-time updates
        self.running = True
        self.update_thread = threading.Thread(target=self.update_data_loop)
        self.update_thread.daemon = True
        self.update_thread.start()

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if selected:
            pid = self.tree.item(selected[0])['values'][0]
            self.selected_pid = pid
            print(f"Selected PID: {pid}")
        else:
            self.selected_pid = None
            print("No selection")

    def update_data_loop(self):
        while self.running:
            self.root.after(0, self.update_data_once)
            time.sleep(self.update_interval)  # Use configurable interval

    def update_data_once(self):
        try:
            self.status_bar.config(text="⏳ Updating...")
            raw_data = self.collector.get_process_data()
            df = process_data(raw_data)

            # Update system summary using NON-BLOCKING CPU monitor
            total_cpu = self.cpu_monitor.get_cpu_percent()  # No blocking!
            memory = psutil.virtual_memory()
            total_memory_percent = memory.percent
            used_memory_gb = memory.used / (1024 ** 3)
            total_memory_gb = memory.total / (1024 ** 3)
            
            # Update labels with better formatting
            self.cpu_label.config(text=f"{total_cpu:.1f}%")
            self.memory_label.config(text=f"{used_memory_gb:.1f} / {total_memory_gb:.1f} GB ({total_memory_percent}%)")
            self.process_count_label.config(text=str(len(df)))

            # Preserve selection
            selected_pid = self.selected_pid
            self.all_processes = df

            # Apply search filter
            search_term = self.search_var.get().strip().lower()
            if search_term:
                self.filtered_processes = self.all_processes[self.all_processes['name'].str.lower().str.contains(search_term, na=False)]
            else:
                self.filtered_processes = self.all_processes

            # Update table
            self.update_table()

            # OPTIMIZED: Update graphs using line data update instead of full redraw
            current_time = time.time()
            if current_time - self.last_graph_update >= 3:
                # Shift data left and add new value (circular buffer approach)
                self.cpu_data.pop(0)
                self.cpu_data.append(total_cpu)
                self.memory_data.pop(0)
                self.memory_data.append(total_memory_percent)

                # Update line data only (much faster than clearing and replotting)
                self.cpu_line.set_ydata(self.cpu_data)
                self.mem_line.set_ydata(self.memory_data)
                
                # Efficient canvas update
                self.canvas.draw_idle()  # draw_idle is more efficient than draw()
                self.last_graph_update = current_time

            self.status_bar.config(text=f"✅ Last Updated: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            # Avoid showing error dialogs during normal operation
            self.status_bar.config(text=f"⚠️ Error: {str(e)[:50]}")

    def update_table(self):
        """Optimized table update with minimal widget operations"""
        selected_pid = self.selected_pid
        
        # Batch delete for better performance
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)

        start_idx = self.current_page * self.processes_per_page
        end_idx = start_idx + self.processes_per_page
        page_data = self.filtered_processes.iloc[start_idx:end_idx]

        # Configure tags once (not every update)
        self.tree.tag_configure("running", background="#166534", foreground="#bbf7d0")
        self.tree.tag_configure("stopped", background="#c2410c", foreground="#ffedd5")
        self.tree.tag_configure("other", background="#854d0e", foreground="#fef08a")

        # Batch insert with values
        for _, row in page_data.iterrows():
            state = row['state']
            tag = "running" if state == "running" else "stopped" if state == "stopped" else "other"
            self.tree.insert('', 'end', values=(row['pid'], row['name'], state, row['cpu_percent'], row['memory_mb'], row['duration']), tags=(tag,))

        # Restore selection
        if selected_pid:
            for item in self.tree.get_children():
                if int(self.tree.item(item)['values'][0]) == selected_pid:
                    self.tree.selection_set(item)
                    break

        total_pages = max(1, (len(self.filtered_processes) + self.processes_per_page - 1) // self.processes_per_page)
        self.page_var.set(f"Page {self.current_page + 1} of {total_pages}")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_table()

    def next_page(self):
        total_pages = (len(self.filtered_processes) + self.processes_per_page - 1) // self.processes_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_table()

    def debounce_search(self, *args):
        if self.search_after_id is not None:
            self.root.after_cancel(self.search_after_id)
        self.search_after_id = self.root.after(300, self.search_processes)

    def search_processes(self):
        try:
            self.current_page = 0
            search_term = self.search_var.get().strip().lower()
            if not search_term:
                self.filtered_processes = self.all_processes
            else:
                self.filtered_processes = self.all_processes[self.all_processes['name'].str.lower().str.contains(search_term, na=False)]
            self.update_table()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to search processes: {str(e)}")

    def clear_search(self):
        self.search_var.set("")
        self.current_page = 0
        self.filtered_processes = self.all_processes
        self.update_table()

    def refresh_now(self):
        print("Refresh Now button clicked")
        try:
            self.update_data_once()
            messagebox.showinfo("Success", "Data refreshed successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh data: {str(e)}")

    def terminate_selected(self):
        print("Terminate Process button clicked")
        try:
            selected = self.tree.selection()
            print(f"Selected items: {selected}")
            if not selected:
                messagebox.showwarning("Warning", "Please select a process to terminate.")
                return
            pid = int(self.tree.item(selected[0])['values'][0])
            print(f"Terminating PID: {pid}")
            success, message = terminate_process(pid)
            if success:
                messagebox.showinfo("Success", message)
                self.selected_pid = None
                self.update_data_once()
            else:
                messagebox.showerror("Error", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to terminate process: {str(e)}")

    def show_details(self):
        print("Show Details button clicked")
        try:
            selected = self.tree.selection()
            print(f"Selected items: {selected}")
            if not selected:
                messagebox.showwarning("Warning", "Please select a process to view details.")
                return
            pid = int(self.tree.item(selected[0])['values'][0])
            print(f"Showing details for PID: {pid}")
            details = get_process_details(pid)
            if "error" in details:
                messagebox.showerror("Error", details["error"])
                self.update_data_once()
            else:
                start_time_str = "N/A"
                start_ts = details.get('start_time')
                if start_ts and start_ts > 1000:
                    try:
                        start_time_str = datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                
                messagebox.showinfo("Process Details", f"Start Time: {start_time_str}\nUser: {details.get('user', 'Unknown')}\nThreads: {details.get('threads', 'Unknown')}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch process details: {str(e)}")
            self.update_data_once()

    def deselect_process(self):
        print("Deselect button clicked")
        self.tree.selection_remove(self.tree.selection())
        self.selected_pid = None
        print("Selection cleared")

    def on_closing(self):
        self.running = False
        self.cpu_monitor.stop()  # Stop the CPU monitor thread
        self.update_thread.join(timeout=2)  # Don't wait forever
        plt.close(self.fig)  # Clean up matplotlib resources
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ProcessMonitorDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()