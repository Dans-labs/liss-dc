# LISS DC

This repo imports LISS DC dataset harvested by the LISS harvester.

### Sample configuration
Copy confiruation file:
```
cp config-sample.py config.py
```
Fill configuration in config.py
```python
# ODISSEI portal
base_url = 'http://dataverse.com/endpoint'
api_token = 'api-token'

dataverse_name = 'dataverse_or_subdataverse_name'
liss_dc_path = '/fullpath/to/liss/metadata'
```

# Run test import process
 * `python test-import_dataset.py`

### Work flow 
 * `python import_dataset.py` will convert and import the datasets
 * `python publish_ds.py` will publish the datasets after check

