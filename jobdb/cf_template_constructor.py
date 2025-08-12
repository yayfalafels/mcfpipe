#!/usr/bin/env python3
"""generates CloudFormation yaml file for DynamoDB tables from DB_SCHEMA JSON file
"""
# dependencies ------------------------------------------------------------------------
import argparse
import json
import re
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


def to_cfn_logical_id(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    pascal = "".join(p[:1].upper() + p[1:] for p in parts if p)
    if not pascal or not pascal[0].isalpha():
        pascal = "T" + pascal
    return pascal


def generate_table_resource(table, table_prefix: str=''):
    stem_name = table.get('table_name', '')
    table_name = f'{table_prefix}{stem_name}' if table_prefix else stem_name
    logical_name = f"{to_cfn_logical_id(stem_name)}Table"

    attr_defs, key_schema = [], []

    def ensure_attr(name, dtype):
        if not any(a["AttributeName"] == name for a in attr_defs):
            attr_defs.append({"AttributeName": name, "AttributeType": dynamodb_type(dtype)})

    # Table keys
    pk = table["primary_key"]
    pk_dtype = next(c for c in table["columns"] if c["column_name"] == pk)["data_type"]
    ensure_attr(pk, pk_dtype)
    key_schema.append({"AttributeName": pk, "KeyType": "HASH"})

    sk = table.get("sort_key")
    if sk:
        sk_dtype = next(c for c in table["columns"] if c["column_name"] == sk)["data_type"]
        ensure_attr(sk, sk_dtype)
        key_schema.append({"AttributeName": sk, "KeyType": "RANGE"})

    # GSIs
    gsi_list = []
    for gsi in table.get("secondary_indexes", {}).get("global", []):
        gpk = gsi["partition_key"]
        gsk = gsi.get("sort_key")
        gpk_dtype = next(c for c in table["columns"] if c["column_name"] == gpk)["data_type"]
        ensure_attr(gpk, gpk_dtype)
        if gsk:
            gsk_dtype = next(c for c in table["columns"] if c["column_name"] == gsk)["data_type"]
            ensure_attr(gsk, gsk_dtype)

        index_name = f"gsi_{gpk}" + (f"_{gsk}" if gsk else "")

        # projection handling
        proj = gsi.get("projection", "ALL")
        proj_type = proj["type"] if isinstance(proj, dict) else str(proj)
        proj_block = {"ProjectionType": proj_type}

        if isinstance(proj, dict) and proj_type.upper() == "INCLUDE":
            attrs = proj.get("attributes", [])
            # DynamoDB limit is 20 non-key attributes for INCLUDE
            if len(attrs) > 20:
                raise ValueError(f"{table_name}:{index_name} INCLUDE has >20 attributes")
            proj_block["NonKeyAttributes"] = attrs

        gsi_entry = {
            "IndexName": index_name,
            "KeySchema": [{"AttributeName": gpk, "KeyType": "HASH"}],
            "Projection": proj_block
        }
        if gsk:
            gsi_entry["KeySchema"].append({"AttributeName": gsk, "KeyType": "RANGE"})

        gsi_list.append(gsi_entry)

    props = {
        "TableName": table_name,
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": attr_defs,
        "KeySchema": key_schema
    }
    if gsi_list:
        props["GlobalSecondaryIndexes"] = gsi_list

    resource_spec = {
            logical_name: {
                "Type": "AWS::DynamoDB::Table", 
                "Properties": props
            }
        }

    return resource_spec


def cf_template_generate(db_schema_path, base_template_path, output_path, table_prefix):
    with open(db_schema_path) as f:
        schema = json.load(f)
        f.close()
    
    resources = {}
    for table in schema["tables"]:
        resources.update(generate_table_resource(table, table_prefix=table_prefix))
    
    with open(base_template_path) as f:
        output = load_yaml(f)
        f.close()

    dynamodb = {"Resources": resources}
    output["Resources"].update(dynamodb["Resources"])
    
    with open(output_path, "w") as f:
        f.write(dump_yaml(output))
        f.close()


# run --------------------------------------------------------------------
def run():
    parser = argparse.ArgumentParser(description="Generate CF from DB schema")
    parser.add_argument("db_schema_path", nargs="?", default=DB_SCHEMA_FILE)
    parser.add_argument("base_yaml_path", nargs="?", default=BASE_YAML_FILE)
    parser.add_argument("output_yaml_path", nargs="?", default=OUTPUT_YAML_FILE)
    parser.add_argument("--env", dest="dev_env", default="", help="Environment tag, e.g. dev, prod")
    parser.add_argument("--project", dest="project_prefix", default="", help="Project prefix, e.g. mcfpipe")
    args = parser.parse_args()

    # Build "<env>_<project>_" only from provided parts; keep underscores for DynamoDB
    parts = [p for p in [args.dev_env, args.project_prefix] if p]
    table_prefix = ("_".join(parts) + "_") if parts else ""

    print(
        "generating YAML file from\n"
        f"schema: {args.db_schema_path}\n"
        f"base CF template: {args.base_yaml_path}\n"
        f"writing to {args.output_yaml_path} ...\n"
        f"table name prefix: '{table_prefix}'"
    )

    cf_template_generate(args.db_schema_path, args.base_yaml_path, args.output_yaml_path, table_prefix)

    print(f"✅ Generated: {args.output_yaml_path}")


if __name__ == "__main__":
    run()