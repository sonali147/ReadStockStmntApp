import os
import json
import uuid
import camelot
import pickle
import datefinder
import pdftotree
import numpy as np
import pandas as pd
import flask
import urllib.parse
import map_prod_name
import pyarrow as pa
from bs4 import BeautifulSoup
from redis import Redis
from flask import request, flash, redirect, render_template, session
from flask.helpers import send_from_directory, url_for
from werkzeug.utils import secure_filename

app = flask.Flask(__name__)
#run_with_ngrok(app)
app.config['SECRET_KEY'] = 'sonali147'
app.config["DEBUG"] = True
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

PREFIX = "/api/v1"

# Redis setup
redis_db = Redis(host='localhost', port=6379, db=1)

#to be read from a file provided by customer
stockist_list = ["PAVAN MEDICAL DISTRIBUTORS", "POORNIMA MEDICAL AGENCIES", "ANUPAMA MEDICAL SYNDICATE"]
sessId = uuid.uuid4().hex


@app.route('/', methods=['GET'])
def home():
    session['id'] = sessId
    return render_template("index.html", stockist=stockist_list)


@app.route('/extractions/<filename>', methods=['GET'])
def show_data(filename):
    return render_template("extractions/html/"+filename)


@app.route('/resolutions/<filename>', methods=['GET'])
def show_data_resolved(filename):
    return render_template("extractions/resolved/"+filename)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route(f'{PREFIX}/upload_file', methods=['POST'])
def extract_invoice():
    try:
        filedata = []
        filenames = []
        fileUploadLink = []
        fileExtractLink = []
        if request.method == 'POST':
            stockist = request.form.get("stockist")
            st_date = "undefined"
            files = request.files.getlist("file[]")
            for f in files:
                if f.filename == "":
                    flash("No file chosen >> filename empty")
                    return redirect(url_for("home", stockist=stockist_list))
                filename = secure_filename(f.filename)
                filename = stockist + "***" + st_date + "***" + filename
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                filepath = extract_data(filename)
                view_file_url = url_for('uploaded_file',filename=filename)
                extract_file_url = "/extractions/" + urllib.parse.quote(filepath)
                redis_db.setex(session['id'], 3600, json.dumps({"session_id":session['id'], 
                                                                "filename":filename,
                                                                "view_file_url":view_file_url,
                                                                "extract_file_url":extract_file_url}))
                filedata.append([filename, view_file_url, extract_file_url])
                filenames.append(filename)
                flash(filename + ' uploaded successfully!')
            return render_template("index.html",
                                    filedata=filedata, 
                                    filenames=filenames,
                                    stockist=stockist_list)
    except FileNotFoundError as e:
        print("Error : ",e)
        return redirect(url_for("home", stockist=stockist_list))


#if file is in uploads folder, call this API
@app.route(f'{PREFIX}/extract_data', methods=['GET'])
def extract_invoice_data():
    filename = request.args.get("filename")
    filepath = "./uploads/"+filename
    #to extract stockist name
    html = pdftotree.parse(filepath)
    soup = BeautifulSoup(html)
    stockist = "test"
    st_date = "undefined"
    try:
        stockist_details = [e.text for e in soup.find_all(["header","section_header"])]
        stockist = stockist_details[0]
        for e in stockist_details:
            dates = list(datefinder.find_dates(e))
            if dates:
                st_date = ""
                for i in dates:
                    st_date += i.strftime("%d-%m-%Y")+"To"
                st_date = st_date[:-2]
    except IndexError as e:
        pass
    prefix = stockist + "***" + st_date + "***"

    tables = camelot.read_pdf(filepath, flavor='stream', pages='1')
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

    return table_html


def extract_data(filename):
    filepath = "./uploads/"+filename

    tables = camelot.read_pdf(filepath, flavor='stream', pages='1-end')
    if "anupama" in filename.lower():
        table_df = tables[1].df
    else:
        table_df = tables[0].df
    
    #dump dataframe in html
    table_html = table_df.to_html()
    html_filepath = "/templates/extractions/html/"
    os.makedirs("."+html_filepath, exist_ok=True)
    fname = filename.replace(".pdf",".html")
    with open("."+html_filepath+fname, "w") as f:
        table_html = "<title>"+fname+"</title>" + "<h3>"+fname+"</h3><br>" + table_html
        f.write(table_html)

    table_df = table_df.rename(columns=table_df.iloc[0]).drop(table_df.index[0])

    #dump dataframe in excel
    excel_filepath = "/templates/extractions/excel/"
    os.makedirs("."+excel_filepath, exist_ok=True)
    fname_xl = filename.replace(".pdf",".xlsx")
    table_df.to_excel("."+excel_filepath+fname_xl, index=False)

    return fname


@app.route(f'{PREFIX}/resolve_products', methods=['GET','POST'])
def resolve_products():
    if request.method == 'GET':
        filename = request.args['filename']
        if redis_db.exists(session['id']):
            file_data = json.loads(redis_db.get(session['id']))
            file_data['resolved_list'], file_data['prod_list'] = map_prod_name.master_resolve(filename)
            print("resolved prods >>", session['id'])
            redis_db.setex(session['id'], 3600, json.dumps(file_data))
            
            if file_data['prod_list']:
                print("ask_user >>> ", file_data['prod_list'])
                return render_template("resolve.html", filename=filename, product_list = enumerate(file_data['prod_list']))
            else:
                flash("No resolutions required")
                return redirect(url_for("home", stockist=stockist_list))
        else:
            flash("No session found, please upload file again !")
            return redirect(url_for("home", stockist=stockist_list))
    else:
        print("resolve post >> ")
        result = {}
        result['form-data'] = {}
        filedata = []
        filenames = []
        for each in request.form:
            print(request.form.getlist(each))
            if each == "filename":
                result[each] = request.form.getlist(each)[0]
            elif each == "session_id":
                result[each] = request.form.getlist(each)[0]
            else:
                result['form-data'][each] = request.form.getlist(each)[0]
        print(result['form-data'])

        if redis_db.exists(session['id']):
            filepath = "./templates/extractions/excel/"
            file_data = json.loads(redis_db.get(result['session_id']))
            filenames = [file_data["filename"]]

            df = pd.read_excel(filepath+file_data['filename'].replace(".pdf", ".xlsx"))
            df = df.iloc[:-1,:]
            df[df.columns[0]].replace(to_replace=["Ipca Activa", "IPCA(ACTIVA)", "IPCA LADORATORIES LTD(ACTIVA)", "IPCA PAIN MANGEMENT",""],value=np.nan, inplace=True)
            df.dropna(axis=0, subset=[df.columns[0]], inplace=True)

            prod_names = df.iloc[:,0]
            print("total len before resolution >> ", len(prod_names))
            final_prods = []
            del_row = []
            for i, prod in enumerate(prod_names):
                for each in file_data['resolved_list']:
                    if prod == each["name"]:
                        final_prods.append(each["match"][1])
                        break
                for idx, each in enumerate(file_data['prod_list']):
                    if prod == each['name']:
                        if result['form-data'][str(idx)] == "Delete Row":
                            del_row.append(i)
                        final_prods.append(result['form-data'][str(idx)])
                        break
            print("total len after resolution >> ", len(final_prods))
            if len(prod_names) == len(final_prods):
                df = df.drop([df.index[e] for e in del_row])
                df.iloc[:,0] = [prod for idx,prod in enumerate(final_prods) if idx not in del_row]
                resolved_file_url = filepath.replace("excel","resolved") + file_data['filename'].replace(".pdf", ".html")
                f = open(resolved_file_url,'w')
                f.write(df.to_html())
                f.close()
                resolved_file_url = resolved_file_url.replace(".html", ".xlsx")
                df.to_excel(resolved_file_url)
                filedata.append([file_data["filename"], file_data["view_file_url"], file_data["extract_file_url"], "/resolutions/"+urllib.parse.quote(file_data['filename'].replace(".pdf", ".html"))])
                flash("Product names resolved successfully - " + "./templates/extractions/resolved/" + file_data['filename'])
            else:
                flash("Some error in resolution --- have a look !")    
        else:
            flash("Session does not exist, please upload file again !")
        return render_template("index.html", 
                                filedata=filedata, 
                                filenames=filenames,
                                stockist=stockist_list)
                


            

    return True

if __name__=="__main__":
    # dir = "./templates/extractions/excel"
    # for f in os.listdir(dir):
    #     os.remove(os.path.join(dir, f))
    # dir = "./templates/extractions/html"
    # for f in os.listdir(dir):
    #     os.remove(os.path.join(dir, f))
    app.run()
    #app.run(host='0.0.0.0', port=5000)
