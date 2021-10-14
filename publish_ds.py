import os
import sys

from pyDataverse.api import Api
import csv
import dvconfig

base_url = dvconfig.base_url
api_token = dvconfig.api_token

api = Api(base_url, api_token)
print('API status: ' + api.status)

all_dataverse_ids = set()
all_dataset_ids = set()


def find_children(dataverse_database_id):
    query_str = '/dataverses/' + str(dataverse_database_id) + '/contents'
    params = {}
    resp = api.get_request(query_str, params=params, auth=True)
    for dvobject in resp.json()['data']:
        dvtype = dvobject['type']
        if 'dataverse' == dvtype:
            dvid = dvobject['id']
            find_children(dvid)
            all_dataverse_ids.add(dvid)
        else:
            dvid = f'{dvobject["protocol"]}:{dvobject["authority"]}/{dvobject["identifier"]}'
            all_dataset_ids.add(dvid)


def publish_dv(dv_ids, ds_ids):
    for i in dv_ids:
        api.publish_dataverse(i, True)
    for i in ds_ids:
        print(f'Publishing {i}')
        resp = api.publish_dataset(i, 'major', True)
        assert 300 > resp.status_code > 199, f'Error: {resp.status_code}, {resp.text}'


def __main__(dv='liss_dc'):
    find_children(dv)

    print(f'len of all ds {len(all_dataset_ids)}')
    print(f'len of all dv {len(all_dataverse_ids)}')
    # exit()

    publish_dv(all_dataverse_ids, all_dataset_ids)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        __main__()
    elif len(sys.argv) == 2:
        __main__(sys.argv[1])
    else:
        exit('wrong number of argments, please specify the dv you want to publish')
