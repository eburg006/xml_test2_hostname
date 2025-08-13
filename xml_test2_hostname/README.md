# xml_test2_gui_v4 (fixed)

Broken-out like your original xml_test2, with a corrected GUI. This fixes the AttributeError for `save_xml` (and includes all toolbar methods).

## Layout
```
xml_test2_gui_v4/
├─ main.py
├─ run_gui.sh
├─ requirements.txt
├─ gui/
│  └─ app_gui.py
├─ core/
│  └─ xml_ro_scpi.py
├─ utils/
│  ├─ __init__.py
│  ├─ discovery.py
│  └─ xml_loader.py
├─ config/
│  ├─ __init__.py
│  └─ keysight_scope.py
└─ test_configs/
   └─ keysight_scope/
```
