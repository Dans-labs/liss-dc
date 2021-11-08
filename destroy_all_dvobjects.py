import argparse
import sys
from pyDataverse.api import Api
import dvconfig
import requests

base_url = dvconfig.base_url
api_token = dvconfig.api_token

api = Api(base_url, api_token)
print('API status: ' + api.status)

dataverse_ids = []
dataset_ids = []


def main(hosting_dv='king', delete_self=False, unpublished=False):
    print("Finding dataverses and datasets to destroy...")
    if unpublished:
        find_unpublished_ds_in_dv(hosting_dv)
    else:
        find_children(hosting_dv)
        dataset_ids.sort(reverse=True)
        for dataset_id in dataset_ids:
            print('Deleting dataset id ' + str(dataset_id))
            print('Preemptively deleting dataset locks for dataset id ' + str(dataset_id))
            resp = requests.delete(base_url + '/api/datasets/' + str(dataset_id) + '/locks?key=' + api_token)
            print(f'For dataset {dataset_id}, status: {resp.status_code}: {resp.text}')
            resp = requests.delete(base_url + '/api/datasets/' + str(dataset_id) + '/destroy?key=' + api_token)
            print(f'For dataset {dataset_id}, status: {resp.status_code}: {resp.text}')
        dataverse_ids.sort(reverse=True)
        for dataverse_id in dataverse_ids:
            print('Deleting dataverse id ' + str(dataverse_id))
            resp = api.delete_dataverse(dataverse_id)
            print(f'For sub dataverse {dataverse_id}, status: {resp.status_code}: {resp.text}')
        if delete_self:
            print('Deleting current hosting dataverse ' + str(hosting_dv))
            resp = api.delete_dataverse(hosting_dv)
            print(f'For main dataverse {hosting_dv}, status: {resp.status_code}: {resp.text}')
        print("Done.")


def find_children(dataverse_database_id):
    query_str = '/dataverses/' + str(dataverse_database_id) + '/contents'
    params = {}
    resp = api.get_request(query_str, params=params, auth=True)
    for dvobject in resp.json()['data']:
        dvtype = dvobject['type']
        dvid = dvobject['id']
        if 'dataverse' == dvtype:
            find_children(dvid)
            dataverse_ids.append(dvid)
        else:
            dataset_ids.append(dvid)


def find_unpublished_ds_in_dv(hosting_dv):
    query_str = f'/search?q=publicationStatus:Unpublished&type=dataset&dataverse={hosting_dv}'
    params = {}
    resp = api.get_request(query_str, params=params, auth=True)
    # exit(resp.json()['data'])
    while len(resp.json()['data']['items']) > 0:
        for dvobject in resp.json()['data']['items']:
            dvid = dvobject['global_id']
            resp = api.get_dataset(f'{dvid}')
            assert 300 > resp.status_code > 199, 'cannot find ds'
            dvid = resp.json()['data']['id']
            resp = requests.delete(base_url + '/api/datasets/' + str(dvid) + '/locks?key=' + api_token)
            print(f'Delete dataset {dvid} lock, status: {resp.status_code}: {resp.text}')
            resp = requests.delete(base_url + '/api/datasets/' + str(dvid) + '/destroy?key=' + api_token)
            print(f'Delete dataset {dvid}, status: {resp.status_code}: {resp.text}')
        resp = api.get_request(query_str, params=params, auth=True)


def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


if __name__ == '__main__':
    if len(sys.argv) == 3:
        hosting_dv = sys.argv[1]
        delete_self = str2bool(sys.argv[2])
        main(hosting_dv, delete_self)
    elif len(sys.argv) == 4:
        hosting_dv = sys.argv[1]
        delete_self = str2bool(sys.argv[2])
        unpublished = str2bool(sys.argv[3])
        main(hosting_dv, delete_self, unpublished)


