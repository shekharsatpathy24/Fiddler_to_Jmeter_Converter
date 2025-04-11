import xml.etree.ElementTree as ET
import zipfile
import os
from collections import defaultdict
from urllib.parse import urlparse

saz_path = r"D:\Projects\Fiddler2Jmeter\saz files\test_fid.saz"

# Create main Test Plan element
jmeter_test_plan = ET.Element('jmeterTestPlan', version="1.2", properties="5.0", jmeter="5.4.1")

# Create the root HashTree
root_hash_tree = ET.SubElement(jmeter_test_plan, 'hashTree')


with zipfile.ZipFile(saz_path, 'r') as saz_zip:
    session_files = [f for f in saz_zip.namelist() if f.endswith("c.txt")]
    for session in session_files:
        with saz_zip.open(session) as f:
            raw = f.read().decode('utf-8', errors='ignore')
            # process raw HTTP session...

def create_header_manager(headers):
    """
    Creates a HeaderManager XML element.
    """
    header_manager = ET.Element('HeaderManager', {
        'guiclass': 'HeaderPanel',
        'testclass': 'HeaderManager',
        'testname': 'HTTP Header Manager',
        'enabled': 'true'
    })
    header_coll = ET.SubElement(header_manager, 'collectionProp', {'name': 'HeaderManager.headers'})
    for name, value in headers.items():
        element_prop = ET.SubElement(header_coll, 'elementProp', {
            'name': name,
            'elementType': 'Header'
        })
        ET.SubElement(element_prop, 'stringProp', {'name': 'Header.name'}).text = name
        ET.SubElement(element_prop, 'stringProp', {'name': 'Header.value'}).text = value
    return header_manager


def create_jmeter_test_plan(sessions):
    """
    Takes a list of session dictionaries (each with keys like method, url, headers, body)
    and generates a valid JMeter .jmx file structure.
    """
    # Create root JMX structure
    jmx_root = ET.Element("jmeterTestPlan", {
        'version': "1.2",
        'properties': "5.0",
        'jmeter': "5.4.1"
    })
    root_hash_tree = ET.SubElement(jmx_root, "hashTree")

    # Test Plan element
    test_plan = ET.SubElement(root_hash_tree, "TestPlan", {
        'guiclass': 'TestPlanGui',
        'testclass': 'TestPlan',
        'testname': 'Test Plan',
        'enabled': 'true'
    })
    ET.SubElement(test_plan, "stringProp", {'name': 'TestPlan.comments'}).text = ''
    ET.SubElement(test_plan, "boolProp", {'name': 'TestPlan.functional_mode'}).text = 'false'
    ET.SubElement(test_plan, "boolProp", {'name': 'TestPlan.serialize_threadgroups'}).text = 'false'
    ET.SubElement(test_plan, "elementProp", {
        'name': 'TestPlan.user_defined_variables',
        'elementType': 'Arguments',
        'guiclass': 'ArgumentsPanel',
        'testclass': 'Arguments',
        'testname': 'User Defined Variables',
        'enabled': 'true'
    })
    ET.SubElement(test_plan, "stringProp", {'name': 'TestPlan.user_define_classpath'})

    test_plan_ht = ET.SubElement(root_hash_tree, "hashTree")

    # Thread Group element
    thread_group = ET.SubElement(test_plan_ht, "ThreadGroup", {
        'guiclass': 'ThreadGroupGui',
        'testclass': 'ThreadGroup',
        'testname': 'Thread Group',
        'enabled': 'true'
    })
    ET.SubElement(thread_group, "stringProp", {'name': 'ThreadGroup.num_threads'}).text = '1'
    ET.SubElement(thread_group, "stringProp", {'name': 'ThreadGroup.ramp_time'}).text = '1'
    ET.SubElement(thread_group, "boolProp", {'name': 'ThreadGroup.scheduler'}).text = 'false'
    thread_group_ht = ET.SubElement(test_plan_ht, "hashTree")

    # Create Transaction Controllers grouped by path prefix
    # transaction_map stores, for each group, the transaction controller’s child hashTree.
    transaction_map = defaultdict(lambda: None)

    for session in sessions:
        method = session['method']
        url = session['url']
        headers = session.get('headers', {})
        body = session.get('body', '')
        host = session.get('host', '')
        protocol = session.get('protocol', 'http')
        port = session.get('port', '')

        # Extract the path (ignore query parameters)
        parsed_url = urlparse(url)
        path = parsed_url.path if parsed_url.path else '/'
        # Use the first segment of the path as the group name. If empty, group under "root"
        group_name = path.strip('/').split('/')[0] if path.strip('/') else 'root'

        # If the transaction for this group doesn't exist, create one.
        if transaction_map[group_name] is None:
            # Create Transaction Controller under thread_group_ht.
            txn = ET.SubElement(thread_group_ht, 'TransactionController', {
                'guiclass': 'TransactionControllerGui',
                'testclass': 'TransactionController',
                'testname': f"{group_name}_txn",
                'enabled': 'true'
            })
            ET.SubElement(txn, 'boolProp', {'name': 'TransactionController.includeTimers'}).text = 'false'
            # Create a hashTree for the Transaction Controller and store it.
            txn_hash_tree = ET.SubElement(thread_group_ht, 'hashTree')
            transaction_map[group_name] = txn_hash_tree
        else:
            txn_hash_tree = transaction_map[group_name]

        # Create HTTPSamplerProxy under the transaction's hashTree.
        http_sampler = ET.SubElement(txn_hash_tree, 'HTTPSamplerProxy', {
            'guiclass': 'HttpTestSampleGui',
            'testclass': 'HTTPSamplerProxy',
            'testname': f"HTTP {method} - {path}",
            'enabled': 'true'
        })
        ET.SubElement(http_sampler, 'stringProp', {'name': 'HTTPSampler.domain'}).text = host
        ET.SubElement(http_sampler, 'stringProp', {'name': 'HTTPSampler.port'}).text = port
        ET.SubElement(http_sampler, 'stringProp', {'name': 'HTTPSampler.protocol'}).text = protocol
        ET.SubElement(http_sampler, 'stringProp', {'name': 'HTTPSampler.path'}).text = path
        ET.SubElement(http_sampler, 'stringProp', {'name': 'HTTPSampler.method'}).text = method
        ET.SubElement(http_sampler, 'boolProp', {'name': 'HTTPSampler.follow_redirects'}).text = 'true'
        ET.SubElement(http_sampler, 'boolProp', {'name': 'HTTPSampler.auto_redirects'}).text = 'false'
        # If method is POST, mark postBodyRaw as true.
        ET.SubElement(http_sampler, 'stringProp',
                      {'name': 'HTTPSampler.postBodyRaw'}).text = 'true' if method == 'POST' else 'false'

        # If there is POST body data, add it as an argument.
        if body:
            element_prop = ET.SubElement(http_sampler, 'elementProp', {
                'name': 'HTTPsampler.Arguments',
                'elementType': 'Arguments',
                'guiclass': 'HTTPArgumentsPanel',
                'testclass': 'Arguments',
                'enabled': 'true'
            })
            coll_prop = ET.SubElement(element_prop, 'collectionProp', {'name': 'Arguments.arguments'})
            arg_prop = ET.SubElement(coll_prop, 'elementProp', {
                'name': '',
                'elementType': 'HTTPArgument'
            })
            ET.SubElement(arg_prop, 'boolProp', {'name': 'HTTPArgument.always_encode'}).text = 'false'
            ET.SubElement(arg_prop, 'stringProp', {'name': 'Argument.value'}).text = body
            ET.SubElement(arg_prop, 'stringProp', {'name': 'Argument.metadata'}).text = '='

        # Create a hashTree for the HTTPSamplerProxy.
        sampler_ht = ET.SubElement(txn_hash_tree, 'hashTree')

        # Add Header Manager if there are headers
        if headers:
            header_mgr = create_header_manager(headers)
            sampler_ht.append(header_mgr)
            # The Header Manager must be followed by its own (empty) hashTree.
            ET.SubElement(sampler_ht, 'hashTree')

    return ET.ElementTree(jmx_root)


# Example dummy session data for testing
sessions = [
    {
        'method': 'GET',
        'url': '/api/v1/users',
        'host': 'httpbin.org',
        'protocol': 'https',
        'headers': {'Authorization': 'Bearer token123', 'User-Agent': 'Mozilla/5.0'},
    },
    {
        'method': 'POST',
        'url': '/api/v1/users/create',
        'host': 'httpbin.org',
        'protocol': 'https',
        'headers': {'Content-Type': 'application/json'},
        'body': '{"name": "Alice"}'
    },
    {
        'method': 'GET',
        'url': 'https://httpbin.org/',
        'host': 'httpbin.org',
        'protocol': 'https',
        'headers': {},
    }
]

# saz_path = r"D:\Projects\Fiddler2Jmeter\saz files\test_fid.saz"
output_path = os.path.join(os.path.dirname(saz_path), "generated_from_saz.jmx")

tree = ET.ElementTree(jmeter_test_plan)
tree.write(output_path, encoding='utf-8', xml_declaration=True)

print(f"✅ JMX generated: {output_path}")
