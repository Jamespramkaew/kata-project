import os, platform, socket
from flask import Flask, render_template, jsonify

app = Flask(__name__)

def meminfo():
    m = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":", 1)
            m[k] = int(v.split()[0])  # kB
    return m

def info():
    m = meminfo()
    total = m["MemTotal"] // 1024
    used = (m["MemTotal"] - m.get("MemAvailable", m["MemFree"])) // 1024
    with open("/proc/uptime") as f:
        up = int(float(f.read().split()[0]))
    return {
        "system": os.environ.get("SYSTEM_NAME", "Kata - Runc Demo"),
        "kernel": platform.release(),
        "cpu": os.cpu_count(),
        "mem_total": total,
        "mem_used": used,
        "mem_pct": round(used * 100 / total) if total else 0,
        "load": " / ".join(f"{x:.2f}" for x in os.getloadavg()),
        "uptime": f"{up // 3600}h {up % 3600 // 60}m",
        "hostname": socket.gethostname(),
    }

@app.route("/")
def index():
    return render_template("index.html", **info())

@app.route("/json")
def as_json():
    return jsonify(info())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
