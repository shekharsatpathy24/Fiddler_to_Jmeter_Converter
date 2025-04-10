# Fiddler_to_Jmeter_Converter
Tool to convert fiddler saz files to jmeter format jmx files 

For converting Fiddler’s .saz (Session Archive ZIP) into a JMeter .jmx file, we are:

1. Parsing the .saz file to extract HTTP requests.

2. Building an XML structure for JMeter using xml.etree.ElementTree.

3. Writing it out to a .jmx file that JMeter can load and run.

