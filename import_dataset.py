import csv
import os
from os.path import join

import lxml.html
from pyDataverse.exceptions import ApiAuthorizationError
from pyDataverse.api import Api
from requests import post
import json
import dvconfig
import lxml.etree as et


base_url = dvconfig.base_url
native_api_base_url = f'{base_url}/api'
api_token = dvconfig.api_token
dataverse_id = dvconfig.dataverse_name
input_path = dvconfig.liss_dc_path
release = 'no'
fail_counter = 0
total_counter = 0

ns = {
    'xmlns': 'http://www.openarchives.org/OAI/2.0/',
    'oai_dc': 'http://www.openarchives.org/OAI/2.0/oai_dc/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
}
api = Api(base_url, api_token)
print('API status: ' + api.status)

# print(f'curl -u {api_token}: {base_url}/dvn/api/data-deposit/v1.1/swordv2/service-document')


def get_primitive_field(list_elements, typeName, typeClass='primitive', multiple=False):
    result = dict()
    result['typeName'] = typeName
    result['multiple'] = multiple
    result['typeClass'] = typeClass
    if not multiple:
        if isinstance(list_elements[0], str):
            result['value'] = list_elements[0]
        else:
            result['value'] = list_elements[0].text
        return result
    else:
        if isinstance(list_elements[0], str):
            result['value'] = [i for i in list_elements]
        else:
            result['value'] = [i.text for i in list_elements]
        return result


def get_compound_field(list_elements, typeName, inner_typeName, typeClass='compound', inner_typeClass='primitive', multiple=True, inner_multiple=False):
    result = dict()
    result['typeName'] = typeName
    result['multiple'] = multiple
    result['typeClass'] = typeClass
    if multiple:
        value_list = list()
        for i in list_elements:
            value_list.append({inner_typeName: get_primitive_field([i], inner_typeName, inner_typeClass, inner_multiple)})
        result['value'] = value_list
        return result
    raise Exception('Does not support compound field with non-multiple value yet')


def get_pid(dom):
    pids = dom.xpath('./dc:identifier', namespaces=ns)
    is_doi: bool = False
    protocol = None
    authority = None
    local_id = None
    if pids is not None and len(pids) == 1:
        print('checking pids')
        pid_uri = pids[0].text
        print(f'checking pids {pid_uri}')
        """if pid uri starts with doi.org set is_doi to True and protocol to doi"""
        if pid_uri.lower().strip().startswith('https://doi.org/'):
            is_doi = True
            protocol = 'doi'
        """get all the components of the uri"""
        pid_components: list = pid_uri.split('/')
        if len(pid_components) == 5:
            authority = pid_components[-2]
            local_id = pid_components[-1]
    return protocol, authority, local_id, is_doi


def convert_dc_to_dv_json(dc_root):
    dc_tags = ['title', 'creator', 'description', 'publisher', 'date', 'identifier', 'rights']
    fields = list()
    """get pid"""
    protocol, authority, local_id, is_doi = get_pid(dc_root)
    pid = f'{protocol}:{authority}/{local_id}'
    if is_doi:
        result = {
            'datasetVersion': {
                "termsOfUse": "N/A",
                'license': 'NONE',
                'protocol': protocol,
                'authority': authority,
                'identifier': pid,
                'metadataBlocks': {
                    'citation': {
                        'displayName': 'Citation Metadata',
                        'fields': [

                        ]
                    }
                }
            }
        }
    else:
        result = {
            'datasetVersion': {
                "termsOfUse": "N/A",
                'license': 'NONE',
                'metadataBlocks': {
                    'citation': {
                        'displayName': 'Citation Metadata',
                        'fields': [

                        ]
                    }
                }
            }
        }

    # get subject
    fields.append(get_primitive_field([f'Social Sciences'], 'subject', 'controlledVocabulary', True))

    # # print(dc_root.xpath('./dc:identifier', namespaces=ns))
    # ids = dc_root.xpath('./dc:identifier', namespaces=ns)
    # if ids is not None and len(ids) > 0:
    #     # result['datasetVersion']['id'] = ids[0].text
    #     fields.append(get_compound_field(ids, 'otherId', 'otherIdValue'))

    # print(dc_root.xpath('./dc:title', namespaces=ns))
    titles = dc_root.xpath('./dc:title', namespaces=ns)
    if titles is not None and len(titles) > 0:
        fields.append(get_primitive_field([titles[0]], 'title'))

    # print(dc_root.xpath('./dc:publisher', namespaces=ns))
    publishers = dc_root.xpath('./dc:publisher', namespaces=ns)
    publisher_dict = dict()
    if publishers is not None and len(publishers) > 0:
        publisher_dict = get_primitive_field(publishers, 'authorAffiliation')

    # print(dc_root.xpath('./dc:creator', namespaces=ns))
    creators = dc_root.xpath('./dc:creator', namespaces=ns)
    if creators is not None and len(creators) > 0:
        creators_dict = get_compound_field(creators, 'author', 'authorName', 'compound', 'primitive', True, False)
        if publisher_dict is not None:
            for i in creators_dict['value']:
                i['authorAffiliation'] = publisher_dict
        fields.append(creators_dict)

    # print(dc_root.xpath('./dc:description', namespaces=ns))
    descriptions = dc_root.xpath('./dc:description', namespaces=ns)
    if descriptions is not None and len(descriptions) > 0:
        fields.append(get_compound_field(descriptions, 'dsDescription', 'dsDescriptionValue', 'compound', 'primitive', True, False))

    # add date as distributionDate
    dates = dc_root.xpath('./dc:date', namespaces=ns)
    if dates is not None and len(dates) > 0:
        fields.append(get_primitive_field(dates, 'distributionDate'))

    # add dataset contact
    fields.append(get_compound_field(['liss@liss.email'], 'datasetContact', 'datasetContactEmail', 'compound', 'primitive', True, False))
    # print(dc_root.xpath('./dc:date', namespaces=ns))
    # print(dc_root.xpath('./dc:rights', namespaces=ns))

    result['datasetVersion']['metadataBlocks']['citation']['fields'] = fields
    return json.dumps(result), is_doi, pid


error_file = '/Users/vic/Documents/DANS/projects/ODISSEI/liss-data/liss-dc/error_file'
def write_error_to_file(resp, others=None):
    with open(error_file, 'a+') as f:
        json.dump(resp.json(), f)
        if others is not None:
            f.writelines(others)
        f.writelines('\n')


def post_request(query_str, metadata=None, auth=False, params=None):
    """Make a POST request.

    Parameters
    ----------
    query_str : string
        Query string for the request. Will be concatenated to
        `native_api_base_url`.
    metadata : string
        Metadata as a json-formatted string. Defaults to `None`.
    auth : bool
        Should an api token be sent in the request. Defaults to `False`.
    params : dict
        Dictionary of parameters to be passed with the request.
        Defaults to `None`.

    Returns
    -------
    requests.Response
        Response object of requests library.

    """
    global fail_counter, total_counter

    url = '{0}{1}'.format(native_api_base_url, query_str)
    if auth:
        if api_token:
            if not params:
                params = {}
            params['key'] = api_token
        else:
            ApiAuthorizationError(
                'ERROR: POST - Api token not passed to '
                '`post_request` {}.'.format(url)
            )
    try:
        data = open(metadata, mode='rb').read()
    except OSError:
        data = metadata

    try:
        resp = post(
            url,
            # data=open(metadata, mode='rb').read(),
            data=data,
            params=params
        )
        if resp.status_code < 200 or resp.status_code > 299:
            fail_counter += 1
            write_error_to_file(resp, )
        return resp
    except ConnectionError:
        raise ConnectionError(
            'ERROR: POST - Could not establish connection to api {}.'
            ''.format(url)
        )


def import_dataset(dataverse, metadata, pid=None, release='no', auth=True):
    query_str = f'/dataverses/{dataverse}/datasets/:import?pid={pid}&release={release}'
    resp = post_request(query_str, metadata, auth)

    if resp.status_code == 201:
        identifier = resp.json()['data']['persistentId']
        print('Dataset {} created.'.format(identifier))
    return resp


def get_titles_from_csv(filename):
    with open(filename, 'r') as csvf:
        rows = csv.reader(csvf)
        return [row[0] for row in rows]


def get_titles():
    liss = '/Users/vic/Documents/DANS/projects/ODISSEI/liss-data/liss-dc/liss panel and immigrant panel - liss.csv'
    immigrant = '/Users/vic/Documents/DANS/projects/ODISSEI/liss-data/liss-dc/liss panel and immigrant panel - immigrant.csv'
    no_arrow = '/Users/vic/Documents/DANS/projects/ODISSEI/liss-data/liss-dc/liss panel and immigrant panel - no_arrow.csv'
    liss_titles = get_titles_from_csv(liss)
    immigrant_titles = get_titles_from_csv(immigrant)
    no_arrow_titles = get_titles_from_csv(no_arrow)
    return liss_titles + immigrant_titles + no_arrow_titles


def main(doi_only=True):
    counter = 1
    all_top_level_titles = get_titles()
    for root, dirs, files in os.walk(input_path):
        for name in files:
            full_input_file = join(root, name)
            if full_input_file.endswith('xml'):
                print(f'{counter} working on {full_input_file}')
                counter += 1
                dom = et.parse(full_input_file)
                xml_root = dom.getroot()
                dc_root = xml_root.xpath('./xmlns:metadata', namespaces=ns)
                title_root = xml_root.xpath('./xmlns:metadata', namespaces=ns)
                title_root = title_root[0].getchildren()
                titles = title_root[0].xpath('./dc:title', namespaces=ns)
                title = titles[0].text

                if isinstance(dc_root, list) and len(dc_root) == 1:
                    dc_root = dc_root[0].getchildren()
                    if isinstance(dc_root, list) and len(dc_root) == 1:
                        if title in all_top_level_titles:
                            print(title)
                            dc_root = dc_root[0]
                            dc_json, is_doi, pid = convert_dc_to_dv_json(dc_root)
                            # print(dc_json)
                            # exit()
                            if is_doi and pid is not None:
                                resp = import_dataset(dataverse_id, dc_json, pid=pid)
                            else:
                                if not doi_only:
                                    resp = api.create_dataset(dataverse_id, dc_json)
                            print(resp.status_code)
                            if not 300 > resp.status_code > 199:
                                print(resp.text)
                                print(dc_json)
                                raise Exception('error occurred')
                        else:
                            print(f'{full_input_file} with title {title} is not top level')
                    else:
                        raise Exception('invalid metadata block, cannot find dc block')
                else:
                    raise Exception('invalid LISS format, cannot find metadata block')
                # exit()


if __name__ == '__main__':
    # import all top level studies
    main()
    # import top level studies with doi
    # main(True)
