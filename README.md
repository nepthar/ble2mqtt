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
