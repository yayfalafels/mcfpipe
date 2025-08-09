#!/usr/bin/env python3
"""generates CloudFormation yaml file for DynamoDB tables from DB_SCHEMA JSON file
"""
# dependencies ------------------------------------------------------------------------
import sys
import json
from cfn_tools import load_yaml, dump_yaml


# constants ---------------------------------------------------------------------------
DB_SCHEMA_FILE = 'db_schema.json'
BASE_YAML_FILE = 'db_api_base.yaml'
OUTPUT_YAML_FILE = 'db_api_stack.yaml'


# helper functions --------------------------------------------------------------------
def dynamodb_type(col_type):
    return {
        "String": "S",
        "Number": "N",
        "Boolean": "BOOL"
    }.get(col_type, "S")


def generate_table_resource(table):
    logical_name = f"{table['table_name'].capitalize()}Table"
    table_name = table["table_name"].replace("_", "-")
    
    attr_defs = []
    key_schema = []

    attr_defs.append({
        "AttributeName": table["primary_key"],
        "AttributeType": dynamodb_type(
            next(col for col in table["columns"] if col["column_name"] == table["primary_key"])["data_type"]
        )
    })
    key_schema.append({
        "AttributeName": table["primary_key"],
        "KeyType": "HASH"
    })

    if "sort_key" in table:
        attr_defs.append({
            "AttributeName": table["sort_key"],
            "AttributeType": dynamodb_type(
                next(col for col in table["columns"] if col["column_name"] == table["sort_key"])["data_type"]
            )
        })
        key_schema.append({
            "AttributeName": table["sort_key"],
            "KeyType": "RANGE"
        })

    return {
        logical_name: {
            "Type": "AWS::DynamoDB::Table",
            "Properties": {
                "TableName": table_name,
                "BillingMode": "PAY_PER_REQUEST",
                "AttributeDefinitions": attr_defs,
                "KeySchema": key_schema
            }
        }
    }


# run --------------------------------------------------------------------
def run(db_schema_path, base_template_path, output_path):
    with open(db_schema_path) as f:
        schema = json.load(f)
        f.close()
    
    resources = {}
    for table in schema["tables"]:
        resources.update(generate_table_resource(table))
    
    with open(base_template_path) as f:
        output = load_yaml(f)
        f.close()

    dynamodb = {"Resources": resources}
    output["Resources"].update(dynamodb["Resources"])
    
    with open(output_path, "w") as f:
        f.write(dump_yaml(output))
        f.close()

    print(f"✅ Generated: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_schema_path = sys.argv[1]
    else:
        db_schema_path = DB_SCHEMA_FILE
    if len(sys.argv) > 2:
        base_yaml_path = sys.argv[2]
    else:
        base_yaml_path = BASE_YAML_FILE
    if len(sys.argv) > 3:
        output_yaml_path = sys.argv[3]
    else:
        output_yaml_path = OUTPUT_YAML_FILE
    print(f'generating YAML file from \nschema: {db_schema_path}\nbase CF template: {base_yaml_path}\nwriting to {output_yaml_path} ...')
    run(db_schema_path, base_yaml_path, output_yaml_path)