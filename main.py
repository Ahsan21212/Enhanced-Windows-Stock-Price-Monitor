import requests
from alpha_vantage.timeseries import TimeSeries
import time
import pandas as pd
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import logging
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

class WindowsStockMonitor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.ts = TimeSeries(key=api_key, output_format='pandas')
        self.running = False
        self.data = {}
        self.thresholds = {}
        self.email_config = None
        
        # Setup logging
        logging.basicConfig(
            filename='stock_monitor.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # GUI
        self.root = tk.Tk()
        self.root.title("Enhanced Windows Stock Price Monitor")
        self.root.geometry("1000x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_gui()

    def setup_gui(self):
        """Setup enhanced GUI"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="5")
        control_frame.pack(fill=tk.X, pady=5)

        # Symbol and threshold inputs
        ttk.Label(control_frame, text="Stock Symbol:").grid(row=0, column=0, padx=5, pady=5)
        self.symbol_entry = ttk.Entry(control_frame)
        self.symbol_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="Upper Threshold:").grid(row=1, column=0, padx=5, pady=5)
        self.upper_entry = ttk.Entry(control_frame)
        self.upper_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="Lower Threshold:").grid(row=2, column=0, padx=5, pady=5)
        self.lower_entry = ttk.Entry(control_frame)
        self.lower_entry.grid(row=2, column=1, padx=5, pady=5)

        # Interval selection
        ttk.Label(control_frame, text="Update Interval (s):").grid(row=3, column=0, padx=5, pady=5)
        self.interval_var = tk.StringVar(value="60")
        self.interval_combo = ttk.Combobox(control_frame, textvariable=self.interval_var, 
                                         values=["30", "60", "120", "300"])
        self.interval_combo.grid(row=3, column=1, padx=5, pady=5)

        # Buttons
        self.start_button = ttk.Button(control_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_button.grid(row=4, column=0, padx=5, pady=5)

        self.stop_button = ttk.Button(control_frame, text="Stop Monitoring", command=self.stop_monitoring, 
                                    state='disabled')
        self.stop_button.grid(row=4, column=1, padx=5, pady=5)

        # Status
        self.status_var = tk.StringVar(value="Status: Idle")
        ttk.Label(main_frame, textvariable=self.status_var).pack(pady=5)

        # Chart frame
        chart_frame = ttk.LabelFrame(main_frame, text="Price Chart", padding="5")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.fig = Figure(figsize=(8, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Alerts frame
        alerts_frame = ttk.LabelFrame(main_frame, text="Alerts", padding="5")
        alerts_frame.pack(fill=tk.X, pady=5)
        self.alerts_list = tk.Listbox(alerts_frame, height=8)
        self.alerts_list.pack(fill=tk.X)

        # Email config button
        ttk.Button(control_frame, text="Configure Email", command=self.configure_email).grid(row=5, column=0, columnspan=2, pady=5)

    def configure_email(self):
        """Email configuration dialog"""
        email_win = tk.Toplevel(self.root)
        email_win.title("Email Configuration")
        email_win.geometry("300x200")

        ttk.Label(email_win, text="Sender Email:").pack(pady=5)
        sender_entry = ttk.Entry(email_win)
        sender_entry.pack(pady=5)

        ttk.Label(email_win, text="Password:").pack(pady=5)
        pass_entry = ttk.Entry(email_win, show="*")
        pass_entry.pack(pady=5)

        ttk.Label(email_win, text="Receiver Email:").pack(pady=5)
        receiver_entry = ttk.Entry(email_win)
        receiver_entry.pack(pady=5)

        def save_email():
            self.email_config = {
                'sender': sender_entry.get(),
                'password': pass_entry.get(),
                'receiver': receiver_entry.get(),
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587
            }
            email_win.destroy()
            messagebox.showinfo("Success", "Email configuration saved")

        ttk.Button(email_win, text="Save", command=save_email).pack(pady=10)

    def fetch_price(self, symbol):
        """Fetch latest stock price with retry logic"""
        for _ in range(3):  # Retry up to 3 times
            try:
                data, _ = self.ts.get_intraday(symbol=symbol, interval='1min')
                if not data.empty:
                    latest_time = data.index[0]
                    latest_price = float(data['4. close'][0])
                    return latest_time, latest_price
            except Exception as e:
                self.logger.error(f"Fetch error for {symbol}: {e}")
                time.sleep(2)  # Wait before retry
        return None, None

    def send_email_alert(self, symbol, price, threshold_type):
        """Send email alert"""
        if not self.email_config:
            return
        
        subject = f"Stock Alert: {symbol} {threshold_type} Threshold"
        body = f"{symbol} price ${price:.2f} crossed {threshold_type} threshold at {datetime.now()}"
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.email_config['sender']
        msg['To'] = self.email_config['receiver']

        try:
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['sender'], self.email_config['password'])
                server.send_message(msg)
            self.logger.info(f"Email alert sent for {symbol}")
        except Exception as e:
            self.logger.error(f"Email send failed: {e}")

    def update_data(self, symbol):
        """Update price data and check thresholds"""
        timestamp, price = self.fetch_price(symbol)
        if price:
            if symbol not in self.data:
                self.data[symbol] = pd.DataFrame(columns=['timestamp', 'price'])
            
            new_data = pd.DataFrame({'timestamp': [timestamp], 'price': [price]})
            self.data[symbol] = pd.concat([self.data[symbol], new_data]).tail(50)
            
            upper = self.thresholds.get(symbol, {}).get('upper')
            lower = self.thresholds.get(symbol, {}).get('lower')
            
            if upper and price > upper:
                alert = f"ALERT: {symbol} ${price:.2f} > ${upper}"
                self.alerts_list.insert(tk.END, alert)
                self.logger.info(alert)
                self.send_email_alert(symbol, price, "upper")
                
            if lower and price < lower:
                alert = f"ALERT: {symbol} ${price:.2f} < ${lower}"
                self.alerts_list.insert(tk.END, alert)
                self.logger.info(alert)
                self.send_email_alert(symbol, price, "lower")
            
            return price
        return None

    def update_chart(self, symbol):
        """Update chart with moving average"""
        if symbol not in self.data or self.data[symbol].empty:
            return
        
        self.ax.clear()
        df = self.data[symbol]
        self.ax.plot(df['timestamp'], df['price'], 'b-', label=f'{symbol} Price')
        
        # Moving average
        ma = df['price'].rolling(window=5).mean()
        self.ax.plot(df['timestamp'], ma, 'r--', label='5-period MA')
        
        # Thresholds
        upper = self.thresholds.get(symbol, {}).get('upper')
        lower = self.thresholds.get(symbol, {}).get('lower')
        if upper:
            self.ax.axhline(y=upper, color='r', linestyle='--', label='Upper')
        if lower:
            self.ax.axhline(y=lower, color='g', linestyle='--', label='Lower')
        
        self.ax.set_title(f'{symbol} Real-time Price with Indicators')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Price ($)')
        self.ax.legend()
        self.ax.grid(True)
        self.ax.tick_params(axis='x', rotation=45)
        self.fig.tight_layout()
        self.canvas.draw()

    def monitoring_loop(self):
        """Main monitoring loop"""
        symbol = self.symbol_entry.get().upper()
        interval = int(self.interval_var.get())
        
        while self.running and symbol:
            price = self.update_data(symbol)
            if price:
                self.status_var.set(f"Status: Monitoring {symbol} - ${price:.2f}")
                self.update_chart(symbol)
            time.sleep(interval)
        
        self.status_var.set("Status: Idle")
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')

    def start_monitoring(self):
        """Start monitoring with validation"""
        symbol = self.symbol_entry.get().upper()
        if not symbol:
            messagebox.showerror("Error", "Please enter a stock symbol")
            return

        try:
            upper = float(self.upper_entry.get()) if self.upper_entry.get() else None
            lower = float(self.lower_entry.get()) if self.lower_entry.get() else None
            if upper and lower and upper <= lower:
                messagebox.showerror("Error", "Upper threshold must be greater than lower threshold")
                return
        except ValueError:
            messagebox.showerror("Error", "Thresholds must be valid numbers")
            return

        self.thresholds[symbol] = {'upper': upper, 'lower': lower}
        if self.running:
            self.stop_monitoring()
        self.running = True
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        
        self.thread = threading.Thread(target=self.monitoring_loop)
        self.thread.start()

    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()

    def on_closing(self):
        """Handle window close"""
        self.stop_monitoring()
        self.root.destroy()

    def run(self):
        """Run the application"""
        self.root.mainloop()

def main():
    API_KEY = "YOUR_API_KEY_HERE"  # Replace with your Alpha Vantage API key
    monitor = WindowsStockMonitor(API_KEY)
    monitor.run()

if __name__ == "__main__":
    main()