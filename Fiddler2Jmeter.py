import zipfile
import os
import xml.etree.ElementTree as ET
import shutil
from urllib.parse import urlparse
import uuid


def parse_saz_file(saz_path, allowed_hosts, allowed_status_codes):
    sessions = []

    with zipfile.ZipFile(saz_path, 'r') as z:
        for name in z.namelist():
            if name.endswith("_c.txt"):
                base = name.replace("_c.txt", "")
                response_file = base + "_s.txt"
                if response_file in z.namelist():
                    try:
                        req_data = z.read(name).decode('utf-8', errors='ignore')
                        res_data = z.read(response_file).decode('utf-8', errors='ignore')

                        # Parse method, URL, headers
                        req_lines = req_data.splitlines()
                        if len(req_lines) < 1:
                            continue

                        method, full_url, _ = req_lines[0].split()
                        parsed_url = urlparse(full_url)
                        host = ""
                        headers = {}
                        post_data = ""
                        header_done = False

                        for line in req_lines[1:]:
                            if line == "":
                                header_done = True
                                continue
                            if not header_done:
                                if ":" in line:
                                    key, val = line.split(":", 1)
                                    key = key.strip()
                                    val = val.strip()
                                    headers[key] = val
                                    if key.lower() == "host":
                                        host = val
                            else:
                                post_data += line + "\n"

                        if host not in allowed_hosts:
                            continue

                        sessions.append({
                            "method": method,
                            "url": full_url,
                            "headers": headers,
                            "post_data": post_data.strip(),
                            "host": host,
                            "path": parsed_url.path
                        })
                    except Exception as e:
                        print(f"Error parsing session {name}: {e}")

    return sessions


def create_header_manager(headers):
    header_manager = ET.Element("HeaderManager", guiclass="HeaderPanel", testclass="HeaderManager", testname="HTTP Header Manager", enabled="true")
    collection_prop = ET.SubElement(header_manager, "collectionProp", name="HeaderManager.headers")
    for name, value in headers.items():
        if value.strip() == "":
            continue
        element_prop = ET.SubElement(collection_prop, "elementProp", name=name, elementType="Header")
        ET.SubElement(element_prop, "stringProp", name="Header.name").text = name
        ET.SubElement(element_prop, "stringProp", name="Header.value").text = value
    return header_manager


def generate_jmx_from_saz(saz_path, allowed_hosts, allowed_status_codes):
    sessions = parse_saz_file(saz_path, allowed_hosts, allowed_status_codes)
    if not sessions:
        raise Exception("No valid sessions found in saz file.")

    ET.register_namespace('', "http://jmeter.apache.org/2021/08/11")
    jmeter_test_plan = ET.Element("jmeterTestPlan", version="1.2", properties="5.0")
    hash_tree_root = ET.SubElement(jmeter_test_plan, "hashTree")

    # Test Plan
    test_plan = ET.SubElement(hash_tree_root, "TestPlan", guiclass="TestPlanGui", testclass="TestPlan", testname="Test Plan", enabled="true")
    ET.SubElement(test_plan, "stringProp", name="TestPlan.comments")
    ET.SubElement(test_plan, "boolProp", name="TestPlan.functional_mode").text = "false"
    ET.SubElement(test_plan, "boolProp", name="TestPlan.serialize_threadgroups").text = "false"
    ET.SubElement(test_plan, "elementProp", name="TestPlan.user_defined_variables", elementType="Arguments", guiclass="ArgumentsPanel", testclass="Arguments", enabled="true")
    ET.SubElement(test_plan, "stringProp", name="TestPlan.user_define_classpath")

    test_plan_hash_tree = ET.SubElement(hash_tree_root, "hashTree")

    # Thread Group
    thread_group = ET.SubElement(test_plan_hash_tree, "ThreadGroup", guiclass="ThreadGroupGui", testclass="ThreadGroup", testname="Thread Group", enabled="true")
    ET.SubElement(thread_group, "stringProp", name="ThreadGroup.on_sample_error").text = "continue"
    ET.SubElement(thread_group, "elementProp", name="ThreadGroup.main_controller", elementType="LoopController", guiclass="LoopControlPanel", testclass="LoopController", enabled="true")
    ET.SubElement(thread_group, "stringProp", name="ThreadGroup.num_threads").text = "1"
    ET.SubElement(thread_group, "stringProp", name="ThreadGroup.ramp_time").text = "1"
    ET.SubElement(thread_group, "boolProp", name="ThreadGroup.scheduler").text = "false"

    tg_hash_tree = ET.SubElement(test_plan_hash_tree, "hashTree")

    # Group by paths
    grouped = {}
    for sess in sessions:
        group_key = sess['path'].split("/")[1] if "/" in sess['path'] else "root"
        if group_key not in grouped:
            grouped[group_key] = []
        grouped[group_key].append(sess)

    for group_name, group_sessions in grouped.items():
        transaction_controller = ET.SubElement(tg_hash_tree, "TransactionController", guiclass="TransactionControllerGui", testclass="TransactionController", testname=group_name, enabled="true")
        ET.SubElement(transaction_controller, "boolProp", name="TransactionController.includeTimers").text = "false"
        trans_hash_tree = ET.SubElement(tg_hash_tree, "hashTree")

        for sess in group_sessions:
            parsed_url = urlparse(sess["url"])
            sampler_name = parsed_url.path if parsed_url.path else "Request"

            http_sampler = ET.SubElement(trans_hash_tree, "HTTPSamplerProxy", guiclass="HttpTestSampleGui", testclass="HTTPSamplerProxy", testname=sampler_name, enabled="true")
            ET.SubElement(http_sampler, "boolProp", name="HTTPSampler.postBodyRaw").text = "true" if sess["method"] != "GET" else "false"
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.domain").text = parsed_url.hostname
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.port").text = str(parsed_url.port) if parsed_url.port else ""
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.protocol").text = parsed_url.scheme
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.path").text = parsed_url.path
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.method").text = sess["method"]
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.follow_redirects").text = "true"
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.auto_redirects").text = "false"
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.use_keepalive").text = "true"
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.DO_MULTIPART_POST").text = "false"
            ET.SubElement(http_sampler, "stringProp", name="HTTPSampler.embedded_url_re").text = ""

            if sess["method"] != "GET":
                arguments = ET.SubElement(http_sampler, "elementProp", name="HTTPsampler.Arguments", elementType="Arguments")
                collection_prop = ET.SubElement(arguments, "collectionProp", name="Arguments.arguments")
                element_prop = ET.SubElement(collection_prop, "elementProp", name="", elementType="HTTPArgument")
                ET.SubElement(element_prop, "boolProp", name="HTTPArgument.always_encode").text = "false"
                ET.SubElement(element_prop, "stringProp", name="Argument.value").text = sess["post_data"]
                ET.SubElement(element_prop, "stringProp", name="Argument.metadata").text = "="
                ET.SubElement(element_prop, "boolProp", name="HTTPArgument.use_equals").text = "true"
                ET.SubElement(element_prop, "stringProp", name="Argument.name")

            sampler_hash_tree = ET.SubElement(trans_hash_tree, "hashTree")
            header_manager = create_header_manager(sess["headers"])
            sampler_hash_tree.append(header_manager)
            ET.SubElement(sampler_hash_tree, "hashTree")

    tree = ET.ElementTree(jmeter_test_plan)
    jmx_path = os.path.splitext(saz_path)[0] + ".jmx"
    tree.write(jmx_path, encoding="utf-8", xml_declaration=True)
    return jmx_path

if __name__ == "__main__":
    saz_file = r"D:\Projects\Fiddler2Jmeter\saz files\test_fid.saz"
    allowed_hosts = ["httpbin.org"]
    allowed_status_codes = [200, 302]  # Optional if you plan to parse status from responses

    output_file = generate_jmx_from_saz(saz_file, allowed_hosts, allowed_status_codes)
    print(f"JMX file generated at: {output_file}")
    
