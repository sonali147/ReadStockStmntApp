import json
import os
import camelot
import pandas as pd
import numpy as np
from copy import deepcopy
from fuzzywuzzy import fuzz


master_names = json.load(open("./resources/product_master_activa.json","r"))


def master_resolve(filename):
    print("master_resolve >>> ", filename)
    filepath = "./templates/extractions/excel/"
    resolved_filepath = "./templates/extractions/resolved/"
    os.makedirs(resolved_filepath, exist_ok=True)
    #files = os.listdir(filepath)
    #resolved_files = os.listdir(resolved_filepath)
    #file_list = list(set(files) - set(resolved_files))

    #handling .Ds_Store file for MacOSX
    #file_list = [file for file in file_list if file != ".DS_Store"]

    df = pd.read_excel(filepath+filename)
    df = df.iloc[:-1,:]
    df[df.columns[0]].replace(to_replace=["Ipca Activa", "IPCA(ACTIVA)", "IPCA LADORATORIES LTD(ACTIVA)", "IPCA PAIN MANGEMENT",""],value=np.nan, inplace=True)
    df.dropna(axis=0, subset=[df.columns[0]], inplace=True)

    prod_names = df.iloc[:,0]
    prod_list = []
    resolved_list = []
    count = 0
    print("Total products ::: ", len(prod_names))
    for prod in prod_names:
        prod_orig = deepcopy(prod)
        print(prod_orig)
        prod = prod.lower()
        resolved_name = ""
        matches = []
        ask_user = []
        for master in master_names:
            ratio = 0
            brand = master["brand"].lower()
            #1. replace "ipca "
            #2. if multiple tokens take 1st
            brand = brand.replace("ipca ", "")
            brand = brand.split()[0]
            if brand in prod:
                productname_orig = deepcopy(master["productname"])
                productname = master["productname"].lower()
                #1. remove -
                ratio = fuzz.partial_ratio(prod, productname)
                #print(prod, " --- ", productname, " ::: ", ratio)
                if ratio > 75:
                    matches.append((prod, productname_orig, ratio))
                else:
                    ask_user.append((prod, productname_orig, ratio))
        if matches:
            resolved_name = sorted(matches, key=lambda x:x[2], reverse=True)[0]
            resolved_list.append({"name":prod_orig, "match":resolved_name})
            count+=1
            #print(prod)
            #print(matches)
            #print(resolved_name)
            #print(" -*- "*10)
        else:
            if not ask_user:
                ask_user = [(prod, prod_orig, 100), (prod, "No Options available", 0)]
            prod_list.append({"name":prod_orig, "options":ask_user})
            # print(prod)
            # print(prod_list)
            # print(" -*- "*10)
    print("Total matches ::: ", count)

    # tips to improve matching :
    # 1. handle "mg" in prod as well as productname
    # 2. handle "-"
    # 3. handle cases like "200tabs" or "200t abs"
    print("map_prod_name >> ", len(resolved_list), " --- ", len(prod_list))

    return resolved_list, prod_list


def extract_data(filename):
    tables = camelot.read_pdf("./uploads/"+filename, flavor='stream', pages='1-end')
    table_df = tables[0].df
    table_df = table_df.rename(columns=table_df.iloc[0]).drop(table_df.index[0])

    #dump dataframe in excel
    excel_filepath = "/templates/extractions/excel/"
    os.makedirs("."+excel_filepath, exist_ok=True)
    fname = filename.split(".")[0]+".xlsx"
    table_df.to_excel("."+excel_filepath+fname, index=False)

    ##dump dataframe in html
    table_html = table_df.to_html()
    html_filepath = "/templates/extractions/html/"
    os.makedirs("."+html_filepath, exist_ok=True)
    fname = filename.split(".")[0]+".html"
    with open("."+html_filepath+fname, "w") as f:
        table_html = "<title>"+fname+"</title>" + "<h3>"+fname+"</h3><br>" + table_html
        f.write(table_html)

    return fname

if __name__=="__main__":
    #extract_data("PAVAN.pdf")
    master_resolve("PAVAN MEDICAL DISTRIBUTORS***undefined***PAVAN.xlsx")