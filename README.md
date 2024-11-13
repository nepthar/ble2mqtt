# ble2mqtt
Broadcast bluetooth beacon data as MQTT messages


# Usage:
To bootstrap/install, use virtualenv:
```
  # make a virutal evn in the current folder
  python3 -m venv ./.venv

  # enter it
  . .venv/bin/activate

  # install all requirements
  pip install -r requirements.txt
```

To scan for devices:
```
  ./run.sh python main.py scan
```

To run indefinitely:
```
  ./run.sh python main.py run
```


1. BLE Beacon broadcast noticed
2. Data turned into key -> value pairs
3. All gauges, updated when received
4.

Hm. Maybe just do the really simple thing and forward them along as gauges? The prometheus client doesn't like programatically generating metrics, but it does say that proxying them is a valid reason. I should look into this.
