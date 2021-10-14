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


def convert_dc_to_dv_json(dc_root):
    dc_tags = ['title', 'creator', 'description', 'publisher', 'date', 'identifier', 'rights']
    fields = list()
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

    # print(dc_root.xpath('./dc:identifier', namespaces=ns))
    ids = dc_root.xpath('./dc:identifier', namespaces=ns)
    if ids is not None and len(ids) > 0:
        # result['datasetVersion']['id'] = ids[0].text
        fields.append(get_compound_field(ids, 'otherId', 'otherIdValue'))

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

    # add dataset contact
    fields.append(get_compound_field(['liss@liss.email'], 'datasetContact', 'datasetContactEmail', 'compound', 'primitive', True, False))
    # print(dc_root.xpath('./dc:date', namespaces=ns))
    # print(dc_root.xpath('./dc:rights', namespaces=ns))

    result['datasetVersion']['metadataBlocks']['citation']['fields'] = fields
    return json.dumps(result)


def __main__():
    counter = 1
    for root, dirs, files in os.walk(input_path):
        for name in files:
            full_input_file = join(root, name)
            if full_input_file.endswith('xml'):
                print(f'{counter} working on {full_input_file}')
                counter += 1
                dom = et.parse(full_input_file)
                xml_root = dom.getroot()
                dc_root = xml_root.xpath('./xmlns:metadata', namespaces=ns)
                if isinstance(dc_root, list) and len(dc_root) == 1:
                    dc_root = dc_root[0].getchildren()
                    if isinstance(dc_root, list) and len(dc_root) == 1:
                        dc_root = dc_root[0]
                        dc_json = convert_dc_to_dv_json(dc_root)
                        print(dc_json)
                        exit()
                        resp = api.create_dataset(dataverse_id, dc_json)
                        print(resp.status_code)
                        if not 300 > resp.status_code > 199:
                            print(resp.text)
                            print(dc_json)
                            raise Exception('error occurred')
                    else:
                        raise Exception('invalid metadata block, cannot find dc block')
                else:
                    raise Exception('invalid LISS format, cannot find metadata block')
                # exit()


if __name__ == '__main__':
    __main__()
