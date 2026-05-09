import time
import random
import threading
import queue
import uuid
import json
from datetime import datetime
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- CONFIGURATION ---
RIDER_LOCATION = {"lat": 19.0760, "lon": 72.8777}  # Fixed Rider Point (Mumbai)
NUM_DRIVERS = 3
SIMULATION_SPEED = 2  
WINDOW_SIZE = 5       

# GLOBAL STATE FOR WEB ACCESS
state = {
    "drivers": {},
    "alerts": [],
    "rider_location": RIDER_LOCATION
}

# --- DATA SERVER (For Frontend) ---
class DataRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # Allow CORS
            self.end_headers()
            self.wfile.write(json.dumps(state).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return # Silent logging

def run_server():
    server = HTTPServer(('localhost', 5001), DataRequestHandler)
    print("Web Data Server running at http://localhost:5001/data")
    server.serve_forever()

# --- MESSAGE BROKER ---
class MessageBroker:
    def __init__(self):
        self.topic = queue.Queue()
    def publish(self, event):
        self.topic.put(event)
    def consume(self):
        return self.topic.get()

# --- EVENT PRODUCER ---
class DriverSimulator(threading.Thread):
    def __init__(self, driver_id, broker):
        super().__init__(daemon=True)
        self.driver_id = driver_id
        self.broker = broker
        self.lat = RIDER_LOCATION["lat"] + random.uniform(-0.02, 0.02)
        self.lon = RIDER_LOCATION["lon"] + random.uniform(-0.02, 0.02)
        self.running = True
        self.battery = 100

    def run(self):
        while self.running:
            try:
                # Occasional stops
                if random.random() > 0.15:
                    self.lat += random.uniform(-0.002, 0.002)
                    self.lon += random.uniform(-0.002, 0.002)
                
                speed = random.uniform(20, 100)
                self.battery -= random.uniform(0.1, 1.0)
                if self.battery < 0: self.battery = 100 # Reset for simulation

                event = {
                    "event_id": str(uuid.uuid4()),
                    "driver_id": self.driver_id,
                    "latitude": round(self.lat, 6),
                    "longitude": round(self.lon, 6),
                    "speed": round(speed, 2),
                    "battery": round(self.battery, 1),
                    "timestamp": datetime.now().isoformat()
                }
                self.broker.publish(event)
                time.sleep(SIMULATION_SPEED)
            except Exception:
                time.sleep(1)

# --- STREAM PROCESSOR ---
class StreamProcessor(threading.Thread):
    def __init__(self, broker):
        super().__init__(daemon=True)
        self.broker = broker
        self.history = {}
        self.stop_counters = {}
        self.processed_ids = set()

    def run(self):
        while True:
            event = self.broker.consume()
            if event['event_id'] in self.processed_ids: continue
            self.processed_ids.add(event['event_id'])
            
            d_id = event['driver_id']
            
            # Sliding Window
            if d_id not in self.history: self.history[d_id] = deque(maxlen=WINDOW_SIZE)
            self.history[d_id].append(event['speed'])
            avg_speed = sum(self.history[d_id]) / len(self.history[d_id])

            # Distance & ETA
            dist = (((event['latitude']-RIDER_LOCATION['lat'])**2 + (event['longitude']-RIDER_LOCATION['lon'])**2)**0.5) * 111
            eta = (dist / event['speed']) * 60 if event['speed'] > 5 else 999

            # Alerts
            alerts = []
            if event['speed'] > 85: alerts.append("Over-speeding!")
            if event.get('battery', 100) < 20: alerts.append("Low Battery!")
            
            prev_data = state['drivers'].get(d_id, {})
            prev_speed = prev_data.get('speed', 0)
            if prev_speed - event['speed'] > 40: alerts.append("Sudden Braking!")

            prev_dist = prev_data.get('distance', 0)
            if dist > prev_dist + 0.5 and dist > 5: alerts.append("Off Route detected!")

            prev_loc = prev_data.get('location')
            curr_loc = [event['latitude'], event['longitude']]
            if prev_loc == curr_loc:
                self.stop_counters[d_id] = self.stop_counters.get(d_id, 0) + 1
            else:
                self.stop_counters[d_id] = 0
            
            if self.stop_counters.get(d_id, 0) >= 10:
                alerts.append("Long Idle Time!")
            elif self.stop_counters.get(d_id, 0) >= 3: 
                alerts.append("Driver Stopped")

            # Update Global State
            state['drivers'][d_id] = {
                "location": curr_loc,
                "speed": event['speed'],
                "battery": event.get('battery', 100),
                "avg_speed": round(avg_speed, 1),
                "eta": round(eta, 1),
                "distance": round(dist, 2),
                "status": "Moving" if event['speed'] > 5 else "Stopped"
            }
            
            if alerts:
                for a in alerts:
                    alert_msg = {"driver_id": d_id, "msg": a, "time": datetime.now().strftime("%H:%M:%S")}
                    state['alerts'].insert(0, alert_msg)
                
                state['alerts'] = state['alerts'][:10] # Keep last 10

            print(f"[Update] Driver {d_id} | ETA: {round(eta,1)}m | Speed: {event['speed']}km/h")

if __name__ == "__main__":
    broker = MessageBroker()
    processor = StreamProcessor(broker)
    processor.start()

    for i in range(1, NUM_DRIVERS + 1):
        DriverSimulator(f"D{i}", broker).start()

    # Start the data server in a new thread
    threading.Thread(target=run_server, daemon=True).start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
