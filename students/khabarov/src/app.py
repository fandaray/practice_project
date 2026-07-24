from flask import Flask, render_template, request, jsonify
from opcua import Client

app = Flask(__name__)


def get_opc_value(tag_name):
    client = Client("opc.tcp://localhost:4840/freeopcua/server/")
    try:
        client.connect()
        boiler = client.get_root_node().get_child(["0:Objects", "2:Boiler"])
        node = boiler.get_child(f"2:{tag_name}")
        val = node.get_value()
        client.disconnect()
        return val
    except Exception as e:
        try:
            client.disconnect()
        except:
            pass
        raise e


def set_opc_value(tag_name, value):
    client = Client("opc.tcp://localhost:4840/freeopcua/server/")
    try:
        client.connect()
        boiler = client.get_root_node().get_child(["0:Objects", "2:Boiler"])
        node = boiler.get_child(f"2:{tag_name}")
        node.set_value(value)
        client.disconnect()
    except Exception as e:
        try:
            client.disconnect()
        except:
            pass
        raise e

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def get_data():
    try:
        curr_temp = get_opc_value("OutputTemp")
        curr_level = get_opc_value("WaterLevel")
        target_temp = get_opc_value("TargetTemp")
        target_level = get_opc_value("TargetLevel")
        auto_mode = get_opc_value("AutoMode")
        controller_type = get_opc_value("ControllerType")

        reached = abs(curr_temp - target_temp) <= 5.0 and abs(curr_level - target_level) <= 5.0

        return jsonify({
            "input_temp_hot": round(get_opc_value("InputTempHot"), 1),
            "input_temp_cold": round(get_opc_value("InputTempCold"), 1),
            "output_temp": round(curr_temp, 1),
            "water_level": round(curr_level, 1),
            "valve_hot": round(get_opc_value("ValveHotIn") * 100, 1),
            "valve_cold": round(get_opc_value("ValveColdIn") * 100, 1),
            "valve_out": round(get_opc_value("ValveOut") * 100, 1),
            "target_temp": target_temp,
            "target_level": target_level,
            "targets_reached": reached,
            "auto_mode": auto_mode,
            "controller_type": controller_type
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/set_valve", methods=["POST"])
def set_valve():
    try:
        name = request.json.get("name")
        value = float(request.json.get("value")) / 100.0
        if name in ["ValveHotIn", "ValveColdIn", "ValveOut"]:
            cmd_tag = name + "Cmd"
            set_opc_value(cmd_tag, value)
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Invalid valve name"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/set_auto", methods=["POST"])
def set_auto():
    try:
        data = request.json
        set_opc_value("TargetTemp", float(data.get("target_temp")))
        set_opc_value("TargetLevel", float(data.get("target_level")))
        set_opc_value("ControllerType", int(data.get("controller_type", 0)))
        set_opc_value("AutoMode", True)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/set_dynamics", methods=["POST"])
def set_dynamics():
    try:
        data = request.json
        set_opc_value("ValveInTravelTime", float(data.get("valve_in_time")))
        set_opc_value("ValveOutTravelTime", float(data.get("valve_out_time")))
        print(f"Настройки успешно записаны в OPC: Вход={data['valve_in_time']}, Выход={data['valve_out_time']}")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=False, port=5000)