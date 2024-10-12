from html.parser import HTMLParser
import html
import json
import os
from pathlib import Path
from typing import TextIO

class TCLDocsParser(HTMLParser):
    def __init__(self, write_fp:TextIO, first:bool):
        super().__init__()
        self.write_fp = write_fp
        self.in_command_name = False
        self.in_command_params = False
        self.in_command_docs = False
        self.first = first
        self.command = {}

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            cls = next((attr[1] for attr in attrs if attr[0] == 'class'), None)
            if not cls:
                return
            if not self.in_command_name and cls == 'memname':
                self.in_command_name = True
                self.command["name"] = None
            elif not self.in_command_params and cls in ('paramtype', 'paramname'):
                self.in_command_params = True
        elif tag == 'div' and ('class', 'memdoc') in attrs:
            self.in_command_docs = True
            self.command["docs"] = ""
        elif self.in_command_docs and tag != "dl":
            self.command['docs'] += f"<{tag}>"
            
    def handle_data(self, data):
        conv_data = html.unescape(data).strip()
        if not conv_data:
            return
        if self.in_command_name:
            self.command['name'] = conv_data
        elif self.in_command_params:
            self.command.setdefault('params', []).append(conv_data)
        elif self.in_command_docs:
            self.command['docs'] += data

    def handle_endtag(self, tag):
        if tag == 'td' and (self.in_command_name or self.in_command_params):
            self.in_command_name = False
            self.in_command_params = False
        elif self.in_command_docs:
            if tag == 'div':
                self.in_command_docs = False
                name = self.command.pop('name')
                command = {name: self.command}
                json_obj = json.dumps(command, indent=4)
                json_obj = json_obj.strip('{}').rstrip('\n')
                if not self.first:
                    self.write_fp.write(",")
                self.first = False
                self.write_fp.write(json_obj)
                self.command = {}
            elif tag != 'dl':
                self.command['docs'] += f"</{tag}>"

def extract_tcl_docs(html_file_path: str, first: bool):
    
    with open(html_file_path, 'r') as f:
        html = f.read()

    with command_file.open("a") as f:   
        parser = TCLDocsParser(f, first)
        parser.feed(html)
        parser.close()


if __name__ == "__main__":
    doc_dir = "P:/Programs/Nuke15.1v2/Documentation/Tcl/" # where the html doc files are
    doc_files = ("group__tcl__builtin", "group__tcl__native") # name of the html doc files
    command_file = Path(__file__).parent.parent.joinpath('tcl_commands.json') # where the json file will be written to
    
    # open the json file and start with an open brace
    with command_file.open("w") as f:
        f.write("{\n")
    
    # 
    first = True
    for doc_file in doc_files: 
        extract_tcl_docs(f"{doc_dir}{doc_file}.html", first)
        first = False
    
    with command_file.open("a") as f:
        f.write("\n}\n")