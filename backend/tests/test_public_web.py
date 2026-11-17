import json
import socket
from unittest.mock import patch
import pytest
from app.public_web import (validate_destination, public_addresses, request_policy,
                            PublicWebError, PublicReader)


@pytest.mark.parametrize('url',[
    'http://yummy-marketplace.com/', 'https://user@yummy-marketplace.com/',
    'https://yummy-marketplace.com:444/', 'https://yummy-marketplace.com.evil.test/',
    'https://127.0.0.1/', 'https://yummy-marketplace.com./',
    'https://yummy-marketplace.com/../admin', 'https://yummy-marketplace.com/%2e%2e/admin',
    'https://yummy-marketplace.com/\\admin', 'https://yummy-marketplace.com/#x',
    'https://yummy-marketplace.com/\n', 'https://[::1]/',
])
def test_reject_destinations(url):
    with pytest.raises(PublicWebError): validate_destination('yummy',url)


@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','169.254.169.254','100.64.0.1','::1','fc00::1','::ffff:8.8.8.8','224.0.0.1'])
def test_reject_nonpublic_and_mapped_answers(ip):
    with patch('socket.getaddrinfo', return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))]):
        with pytest.raises(PublicWebError):public_addresses('yummy-marketplace.com')


def test_reject_mixed_dns():
    with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443)),(2,1,6,'',('10.0.0.1',443))]):
        with pytest.raises(PublicWebError):public_addresses('yummy-marketplace.com')


@pytest.mark.parametrize('method,path',[
    ('POST','/orders'),('DELETE','/productos'),('PUT','/perfil'),('GET','/checkout'),
    ('GET','/mensajes'),('GET','/admin'),('GET','/assets/../../api/delete'),
])
def test_no_commitment_or_account_endpoints(method,path):
    with pytest.raises(PublicWebError):request_policy('yummy','https://yummy-marketplace.com'+path,method)


def test_search_body_reconstructed_without_identifiers():
    _,body=request_policy('yummy','https://api.yummy-marketplace.com/search/v1/posts','POST',
        '{"query":"audifonos","page":0,"hitsPerPage":60,"filters":{"includeBusinessPosts":true,"sortBy":"relevance"}}',query='audifonos')
    assert json.loads(body)=={'query':'audifonos','page':0,'hitsPerPage':12,'filters':{'includeBusinessPosts':True}}
    with pytest.raises(PublicWebError):
        request_policy('yummy','https://api.yummy-marketplace.com/search/v1/posts','POST','{"query":"unrelated"}',query='audifonos')
    with pytest.raises(PublicWebError):
        request_policy('yummy','https://api.yummy-marketplace.com/search/v1/posts','POST','{"query":"audifonos","token":"no"}',query='audifonos')


def test_readonly_api_and_bucket_isolation():
    for u in ['https://api.yummy-marketplace.com/orders','https://storage.googleapis.com/other-bucket/file.jpg',
              'https://firebasestorage.googleapis.com/v0/b/other/o/posts%2Fa']:
        with pytest.raises(PublicWebError):request_policy('yummy',u)
    request_policy('yummy','https://storage.googleapis.com/fortodos-1a822.appspot.com/uploads/example.jpg')
    request_policy('yummy','https://api.yummy-marketplace.com/config/get-config')


def test_budget_applies_before_network():
    reader=PublicReader('mitickera',max_requests=0)
    with patch('app.public_web.public_addresses') as dns:
        with pytest.raises(PublicWebError):reader.fetch('https://mitickera.com/eventos/')
        dns.assert_not_called()
