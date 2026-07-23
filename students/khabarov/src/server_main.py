from flask import Flask, render_template, request, jsonify
from opcua import Client

app = Flask(__name__)

client = Client("opc.tcp://localhost:4840/freeopcua/server/")
client.connect()

boiler = client.get_root_node().get_child(["0:Objects", "2:Boiler"])

nodes = {
    "InputTempHot": boiler.get_child("2:InputTempHot"),
    "InputTempCold": boiler.get_child("2:InputTempCold"),
    "OutputTemp": boiler.get_child("2:OutputTemp"),
    "WaterLevel": boiler.get_child("2:WaterLevel"),
    "ValveHotIn": boiler.get_child("2:ValveHotIn"),
    "ValveColdIn": boiler.get_child("2:ValveColdIn"),
    "ValveOut": boiler.get_child("2:ValveOut"),
    "AutoMode": boiler.get_child("2:AutoMode"),
    "TargetTemp": boiler.get_child("2:TargetTemp"),
    "TargetLevel": boiler.get_child("2:TargetLevel"),
    # Новые ноды настроек
    "ValveInTravelTime": boiler.get_child("2:ValveInTravelTime"),
    "ValveOutTravelTime": boiler.get_child("2:ValveOutTravelTime"),
}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def get_data():
    try:
        return jsonify({
            "input_temp_hot": round(nodes["InputTempHot"].get_value(), 1),
            "input_temp_cold": round(nodes["InputTempCold"].get_value(), 1),
            "output_temp": round(nodes["OutputTemp"].get_value(), 1),
            "water_level": round(nodes["WaterLevel"].get_value(), 1),
            "valve_hot": round(nodes["ValveHotIn"].get_value() * 100, 1),
            "valve_cold": round(nodes["ValveColdIn"].get_value() * 100, 1),
            "valve_out": round(nodes["ValveOut"].get_value() * 100, 1),
            "auto_mode": nodes["AutoMode"].get_value(),
            "target_temp": round(nodes["TargetTemp"].get_value(), 1),
            "target_level": round(nodes["TargetLevel"].get_value(), 1)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/set_valve", methods=["POST"])
def set_valve():
    try:
        name = request.json.get("name")
        value = float(request.json.get("value")) / 100
        if name in ["ValveHotIn", "ValveColdIn", "ValveOut"]:
            cmd_name = name + "Cmd"
            boiler.get_child(f"2:{cmd_name}").set_value(value)
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Invalid valve name"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/set_auto", methods=["POST"])
def set_auto():
    try:
        data = request.json
        nodes["TargetTemp"].set_value(float(data.get("target_temp")))
        nodes["TargetLevel"].set_value(float(data.get("target_level")))
        nodes["AutoMode"].set_value(True)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/set_dynamics", methods=["POST"])
def set_dynamics():
    try:
        data = request.json
        in_time = float(data.get("valve_in_time"))
        out_time = float(data.get("valve_out_time"))

        nodes["ValveInTravelTime"].set_value(in_time)
        nodes["ValveOutTravelTime"].set_value(out_time)

        print(f" Динамика обновлена: Вход={in_time}с, Выход={out_time}с")
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f" Ошибка сохранения: {e}")
        return jsonify({"error": str(e)}), 500
