#!/usr/bin/env python3
#######################################################################################################################
# Generate DNS Zone file from Namecheap
#
# Modification History:
# Date         Version   Modified by          Github URL                           Description
# 2016-03-11   1.0       Judotens Budiarto    https://github.com/judotens          Initial creation
# 2020-01-17   1.1       Andrew               https://github.com/andrew-nuwber     Resolve CAPTCHA issue
# 2020-12-07   1.2       Dinis                https://github.com/dlage             Cloudflare and AAAA record support
# 2022-08-30   1.3       Ashley Kleynhans     https://github.com/ashleykleynhans   Python3 and more DNS records support,
#                                                                                  Refactored code to break out of loop
#                                                                                  sooner, use argparse to validate
#                                                                                  command line arguments, option to
#                                                                                  choose default or cloudflare format.
#                                                                                  improved error handling, autodetect
#                                                                                  domain name.
#######################################################################################################################
"""
1. Login to Namecheap Account
2. Get JSON from https://ap.www.namecheap.com/Domains/dns/GetAdvancedDnsInfo?fillTransferInfo=false&domainName=YOURDOMAINNAME.com
3. Save it to file
4. `python get_namecheap_dns_records.py data.json`
"""
import argparse
import json

RECORD_TYPES = {
    1: 'A',
    2: 'CNAME',
    3: 'MX',
    5: 'TXT',
    8: 'AAAA',
    9: 'NS',
    10: 'URL Redirect',
    11: 'SRV',
    12: 'CAA',
    13: 'ALIAS'
}


def get_args():
    parser = argparse.ArgumentParser(
        description='Get Namecheap DNS records.',
    )

    parser.add_argument(
        'filename',
        type=str,
        help='Filename'
    )

    parser.add_argument(
        '--format', '-format', '--f', '-f',
        type=str,
        required=False,
        default='default',
        choices={'default', 'cloudflare'},
        help='Output format (default/cloudflare)'
    )

    return parser.parse_args()


def parse_dns_info(dns_info, output_format):
    items = []

    if 'Result' in dns_info and\
    'CustomHostRecords' in dns_info['Result'] and\
    'Records' in dns_info['Result']['CustomHostRecords']:
        records = dns_info['Result']['CustomHostRecords']['Records']
    else:
        raise KeyError('JSON is in an unexpected format')

    if not len(records):
        raise Exception('No DNS records found in JSON')

    for record in records:
        # Skip inactive records
        if not record['IsActive']:
            continue

        # Skip unknown record types
        if record['RecordType'] not in RECORD_TYPES.keys():
            continue

        record_type = RECORD_TYPES[record['RecordType']]
        value = record['Data']
        host = record['Host']

        if record_type == 'MX':
            value = f"{record['Priority']} {value}"
        elif record_type == 'TXT':
            value = f'"{value}"'

        if output_format == 'cloudflare':
            domain = dns_info['Result']['DomainBasicDetails']['DomainName']
            if host == '@':
                host = domain
            else:
                host = f'{host}.{domain}.'

        items.append([
            host,
            str(record['Ttl']),
            'IN',
            record_type,
            value
        ])

    return items


if __name__ == '__main__':
    try:
        args = get_args()
        filename = args.filename
        output_format = args.format
        file = open(filename, 'r')
        dns_info = json.loads(file.read())
        file.close()
        records = parse_dns_info(dns_info, output_format)

        for record in records:
            print('\t'.join(record))
    except (IOError, KeyError, Exception) as e:
        print(f'ERROR: {e}')
    except json.decoder.JSONDecodeError as e:
        print(f'ERROR: Unable to decode JSON from {filename}: {e}')