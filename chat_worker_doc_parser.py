import re
import os
import pdb
import csv
import inspect
import json
import time
import redis
import datetime
import requests
#import python3_gearman
#import dialogflow_v2 as dialogflow
import pandas as pd
import traceback
import uuid 

from fuzzywuzzy import fuzz
from datetime import date
from pymongo import MongoClient
#from google.api_core.exceptions import InvalidArgument
#from google.cloud import documentai_v1beta2 as documentai
#from google.cloud import vision, storage
#from google.cloud.vision import types
#from google.protobuf import json_format
from messytables import CSVTableSet, XLSTableSet, type_guess, types_processor, headers_guess, headers_processor,offset_processor

DIALOGFLOW_PROJECT_ID = 'voicebot-dsyodm'
DIALOGFLOW_LANGUAGE_CODE = 'en-IN'
# GOOGLE_APPLICATION_CREDENTIALS = './voicebot-dsyodm-1e2152833343.json'
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
GOOGLE_APPLICATION_CREDENTIALS = r'./resources/docparser_vision_doc_ai.json'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS


class chatworker():
    
    def __init__(self,):
        print ("===in init===")
        self.context_dict = {}
        
        self.redis_db = redis.Redis(db = 1)
        #self.mongo_client = MongoClient('mongodb://localhost:27017/')
        #self.mongo_db = self.mongo_client['DocumentParser']
        self.stockist_list = json.load(open("./resources/stockist_list.json","r"))
        self.product_master_activa = json.load(open("./resources/product_master_activa.json", 'r'))
        self.excel_mapping = json.load(open("./resources/excel_mapping.json", 'r'))
        #gm_worker = python3_gearman.GearmanWorker(['localhost:4730'])
        #gm_worker.register_task('doc_parser_main', self.main)
        #gm_worker.register_task('get_qc_data', self.getQCData)
        #gm_worker.register_task('update_qc_data', self.updateQCData)
        #gm_worker.work()
    
       
    # def getUserData(self,doc_id, login_id):
    #     print("===in getUserData===", login_id)
    #     data = {}
    #     collected_data = {}
    #     if login_id:
    #         context_id = login_id + "_doc_parser"
    #     elif doc_id:
    #         context_id = doc_id + "_doc_parser"
    #     if context_id and self.redis_db.exists(context_id):
    #         print("data found in redis")
    #         data = json.loads(self.redis_db.get(context_id))
    #         if data.get("pre_context_id", ""):
    #             context_id = data.get("pre_context_id", "")
    #         collected_data = data.get("collected_data", {})
    #     else:
    #         data = {}
    #         data["collected_data"] = {}
    #         self.redis_db.setex(context_id, 3600, json.dumps(data))
        
    #     print("context_id: ", context_id )
    #     print ("user data :", json.dumps(data, indent =4))
    #     return data , collected_data, context_id
    
    # def upload_documents(self,data):
    #     # url = "https://api.docparser.com/v1/document/fetch/jvagmyzcnfld"
    #     # api_key = "6413cf21ce4494d3d7566ea790dee9d31f3dd79b"
    #     url = "https://api.docparser.com/v1/document/fetch/fwnhfrbovgja"
    #     api_key = "38da0ac7490483183063c0efa8f70d7aef90678b"
    #     payload = {"url": data["url"]}
    #     headers = {
    #         'api_key': api_key
    #     }
    #     response = requests.request("POST", url, data=payload, headers=headers)
    #     upload_details = response.json()
    #     return  upload_details
    
    def excel_extractor(self, path, file_type, stockist_data):
        table_data = []
        table_df = pd.DataFrame(table_data)
        n = 1
        discard_list = []
        break_condition = "abracadabra"
        headers = []
        drop_cols = []
        print(file_type)
        try:
            fh = open(path, 'rb')
            table_set = ""
            stockist = stockist_data.get("stockist", "")
            if file_type == ".xls" or file_type == ".xlsx":
                table_set = XLSTableSet(fh)
            elif file_type == ".csv":
                table_set = CSVTableSet(fh)
            row_set = table_set.tables[0]    
            offset, headers = headers_guess(row_set.sample)
            if stockist and stockist in self.excel_mapping:
                if self.excel_mapping[stockist].get("offset",None):
                    n = int(self.excel_mapping[stockist]["offset"])
                if self.excel_mapping[stockist].get("break",None):
                    break_condition = self.excel_mapping[stockist]["break"]
                if self.excel_mapping[stockist].get("headers",None):
                    headers = self.excel_mapping[stockist]["headers"]
                if self.excel_mapping[stockist].get("discard_list",None):
                    discard_list = self.excel_mapping[stockist]["discard_list"]
                if self.excel_mapping[stockist].get("drop_cols",None):
                    drop_cols = self.excel_mapping[stockist]["drop_cols"]
            row_set.register_processor(headers_processor(headers))
            row_set.register_processor(offset_processor(offset + n))
            types = type_guess(row_set.sample, strict=True)
            row_set.register_processor(types_processor(types))
            for row in row_set.dicts():
                row = dict(row)
                temp = {}
                for k,v in row.items():
                    if isinstance(k, str) and not k.startswith("column_"):
                        if k.upper() in ["PRODUCT DESCRIPTION", "NAME","PRODUCT NAME", "ITEM DESCRIPTION"]:
                            k = "item"
                        k = k.lower().replace(".", "")
                        if k == "item" and not v :
                            break
                        if v is not None and not isinstance(v, str) and not isinstance(v, datetime.datetime):
                            v = float(round(v,2))
                        temp[k] = v
                        if discard_list:
                            if isinstance(v, str) and any(v.lower().startswith(each) for each in discard_list):
                                temp = {}
                                break
                if temp.get("item","").strip():
                    if temp["item"].strip().startswith(break_condition):
                        break
                    elif temp["item"].upper() not in ["TOTAL", "TOTAL VALUE"]:
                        table_data.append(temp)
            if table_data:
                table_df = pd.DataFrame(table_data)
                table_df.drop(table_df.columns[drop_cols], axis = 1, inplace = True)
        except Exception as e:
                print("Exception in {}".format(inspect.stack()[0][3]))
                print(traceback.format_exc())
        return table_df
    
    # def upload_blob_process_data(self, bucket_name, source_file_name, destination_blob_name,stockist_name):
    #     """Uploads a file to the bucket."""
    #     # bucket_name = "your-bucket-name"
    #     # source_file_name = "local/path/to/file"
    #     # destination_blob_name = "storage-object-name"
    
    #     storage_client = storage.Client()
    #     bucket = storage_client.bucket(bucket_name)
    #     blob = bucket.blob(destination_blob_name)
    
    #     blob.upload_from_filename(source_file_name)
    
    #     print(
    #         "File {} uploaded to {}.".format(
    #             source_file_name, destination_blob_name
    #         )
    #     )
        
    #     """ Run vision API """
        
    #     project_id='docparser-pewl'
    #     input_uri = 'gs://doc_etraction/{}'.format(destination_blob_name)
        
    #     client = documentai.DocumentUnderstandingServiceClient()
    #     gcs_source = documentai.types.GcsSource(uri=input_uri)
    #         # mime_type can be application/pdf, image/tiff,
    #         # and image/gif, or application/json
    #     input_config = documentai.types.InputConfig(
    #         gcs_source=gcs_source, mime_type='application/pdf')
        
    #     table_extraction_params = documentai.types.TableExtractionParams(enabled=True)
    #     parent = 'projects/{}/locations/us'.format(project_id)
    #     request = documentai.types.ProcessDocumentRequest(
    #             parent=parent,
    #             input_config=input_config)#,
    #     #         table_extraction_params=table_extraction_params)
    #     document = client.process_document(request=request)
        
    #     def _get_text(el, cells_type = 0):
    #         """Convert text offset indexes into text snippets.
    #         """
    #         response = ''
    #         # If a text segment spans several lines, it will
    #         # be stored in different text segments.
    #         for segment in el.text_anchor.text_segments:
    #             start_index = segment.start_index
    #             end_index = segment.end_index
    #             response += document.text[start_index:end_index]
    #         response = response.strip('\n')
    #         response = response.strip()
    #         if cells_type:
    #             response = response.replace(".", "_")
    #             response = response.replace(":","")
    #             response = response.lower()
    #         return response
        
    #     table_dict = {}
    #     table_num = 'table'
    #     table_dict[table_num] = []
        
    #     for page in document.pages:
    #         print('Page number: {}'.format(page.page_number))
    #     #     pdb.set_trace()
    #         for table_num, table in enumerate(page.tables):
    #             table_num = 'table'
    #             if page.page_number == 1:
    #                 for row_num, row in enumerate(table.header_rows):
    #                     cells = [_get_text(cell.layout,1).replace("\n","_") for cell in row.cells]
    #                     if stockist_name[0] in [ "HANJI MEDICALS","hanji_medicals"]:
    #                         temp_cells = []
    #                         count = 0
    #                         for a in cells:
    #                             if count == 7:
    #                                 split_element = a.split("_")
    #                                 temp_cells.append("_".join(split_element[2:]))
    #                                 temp_cells.append("_".join(split_element[-2:]))
    #                             else:
    #                                 temp_cells.append(a)
    #                             count += 1
    #                         cells = temp_cells
    #                     table_dict[table_num].append(cells)
    #     #                 print('Header Row {}: {}'.format(row_num, cells))
    #             for row_num, row in enumerate(table.body_rows):
    #                 cells = [_get_text(cell.layout) for cell in row.cells]
                    
    #                 if stockist_name[0] in [ "HANJI MEDICALS","hanji_medicals"] and len(cells) == 10:
    #                     count = 0
    #                     temp_cells = []
    #                     for a in cells:
    #                         if count == 7:
    #                             split_element = a.split()
    #                             for i in split_element:
    #                                 temp_cells.append(i)
    #                         else:
    #                             temp_cells.append(a)
    #                         count += 1
    #                     cells = temp_cells
    #                     if len(cells) == 13:
    #                         cells = []
    #                 if "Total" not in cells and cells: 
    #                     table_dict[table_num].append(cells)
    #     #             print('Row {}: {}'.format(row_num, cells))
    #     column_names = table_dict['table'].pop(0)
    #     df = pd.DataFrame(table_dict['table'], columns=column_names)
    #     result = df.to_json(orient="records")
    #     result = json.loads(result)
    #     final_table = []
        
    #     for doc in result:
    #         if "product" in doc:
    #             doc["item"] = doc["product"]
    #             del doc["product"]
    #         if "product name" in doc:
    #             doc["item"] = doc["product name"]
    #             del doc["product name"]
    #         final_table.append(doc)
    #     print ('result', result)
    #     print ('final_table', final_table)
    #     return final_table
        
        
    # def mongoDump(self, data, collection_name, many=0):
    #     # pdb.set_trace()
    #     collection = self.mongo_db[collection_name]
    #     if many:
    #         collection.insert_many(data)
    #         for doc in data:
    #             if "_id" in doc:
    #                 del doc["_id"]
    #     else:
    #         collection.insert_one(data)
    #         if "_id" in data:
    #             del data["_id"]
    #     print("data dumped into : ", collection_name)
    
    # def getStockistData(self, stockist_name):
    #     collection = self.mongo_db["ResolvedProducts"]
    #     data = collection.find_one({"stockist": stockist_name})
    #     if not data:
    #         data = {"stockist": stockist_name}
    #     if "_id" in data:
    #         del data["_id"]
    #     return data
    
    # def updateStockistData(self, stockist_data):
    #     collection = self.mongo_db["ResolvedProducts"]
    #     collection.update({"stockist": stockist_data["stockist"]}, stockist_data, upsert=True)
    #     print ("updated stockist data")
    
    # def getQCData(self, gearman_worker, gearman_job):
    #     data = []
    #     req_data = json.loads(gearman_job.data)
    #     print ("in get QC", req_data)
    #     collection = self.mongo_db["processedDocuments"]
    #     cursor = collection.find(req_data, {"_id": 0})
    #     for doc in cursor:
    #         data.append(doc)
    #     print ("mongo", data)
    #     return json.dumps(data)
    
    # def updateQCData(self, gearman_worker, gearman_job):
    #     data = {}
    #     req_data = json.loads(gearman_job.data)
    #     collection = self.mongo_db["processedDocuments"]
    #     for doc in req_data:
    #         if not doc.get("item",""):
    #             data["Error"] = "item not found, update failed"
    #             break
    #         if not  doc.get("document_id",""):
    #             data["Error"] = "document_id not found, update failed"
    #             break
    #         collection.update({"item": doc.get("item", ""),"document_id": doc.get("document_id", "") }, doc)
    #         data["status"] = "updated documents"
    #     print ("in update QC", req_data)
    #     return json.dumps(data)
            
    # def process_parsed_data(self, data, stockist_data):
    #     processed_data = []
    #     self.mongoDump(data, "parsedDocuments")
    #     product_data = data["product_table"]
    #     difference_count = 0
    #     temp_dict = {}
    #     temp_dict["document_id"] = data["document_id"]
    #     temp_dict["type"] = "summary"
    #     temp_dict["address"] = data.get("address",{})
    #     temp_dict["totals"] = data.get("totals",{})
    #     temp_dict["name"] = data.get("name","")
    #     temp_dict["company_name"] = data.get("company_name","")
    #     temp_dict["date"] = data.get("date",{})
        
    #     for prod in product_data:
    #         uploaded_name = prod["item"]
    #         prod["resolved_name"] = ""
    #         prod["document_id"] = data["document_id"]
    #         prod["type"] = "product_table"
    #         # print ("\n\n for product : ", uploaded_name)
    #         if uploaded_name in stockist_data:
    #             prod["resolved_name"] = stockist_data[uploaded_name]
    #         else:
    #             difference_count += 1
    #             top_score = 0
    #             temp = []
    #             ask_user = ["No Option Available"]
    #             # op_count = 1
    #             for doc in self.product_master_activa:
                    
    #                 master_name = doc["productname"]
    #                 brand = doc["brand"]
    #                 ratio = fuzz.ratio(uploaded_name.lower(),master_name.lower())
    #                 if ratio >= top_score :
    #                     top_score = ratio
    #                 temp.append((uploaded_name, master_name, ratio, brand))
    #             for tup in temp:
    #                 append_status = False
    #                 if tup[2] >= top_score - 20:
    #                     up_name = re.sub('[^A-Za-z0-9]+', ' ', tup[0].lower()).split()
    #                     for txt in up_name:
    #                         if txt in tup[3].lower():
    #                             append_status = True
    #                             break
                      
    #                 if append_status:
    #                     ask_user.append(tup[1])
    #             prod["ask_user"] = ask_user
    #         processed_data.append(prod)
        
    #     data["product_table"] = processed_data
    #     # print("\n\n processed_data: ", json.dumps(data, indent=2))
    #     data["difference_count"] = difference_count
    #     self.mongoDump(processed_data, "processedDocuments", 1)
    #     self.mongoDump(temp_dict, "processedDocuments")
    #     return data
    
    # def completeMapping(self, data, resp_text=""):
    #     print ("===in completeMapping===")
    #     prod = data["product_table"]
    #     date = data.get("date",{})
    #     address = data.get("address",{})
    #     totals =  data.get("totals",{})
    #     doc_details = {
    #         "Document ID":data.get("document_id",""),
    #         "Name": data.get("name", ""),
    #         "Company Name": data.get("company_name","")
    #         }
        
    #     count = 1
    #     for doc in date:
    #         doc_details["Date " + str(count)] = doc['formatted']
    #         count += 1
            
    #     for k,v in totals.items():
    #         k = " ".join(k.split("_")).title()
    #         doc_details[k] = v
        
    #     prod_match = []
    #     for doc in prod:
    #         temp_dict = {}
    #         temp_dict["Product Name"] = doc["item"]
    #         count_op = 1
    #         for item in doc["ask_user"]:
    #             temp_dict["Option " + str(count_op)] = item
    #             count_op += 1
    #         prod_match.append(temp_dict)
    #         del doc["ask_user"]

    #     keys = []
    #     values = []
    #     for k,v in doc_details.items():
    #         keys.append(k)
    #         values.append(v)
    #     keys.append("Address")
    #     values.append("")
        
    #     for k,v in address.items():
    #         keys.append(k)
    #         values.append(v)
        
    #     doc_details = {"Fields" : keys, "Values":values}
    #     prod_df = pd.DataFrame(prod)
    #     prod_match_df = pd.DataFrame(prod_match)
    #     doc_df = pd.DataFrame(doc_details)
    #     # path = "../../WhatsApp-master/parsedDocuments/"+ data["document_id"]
    #     path = "../parsedDocuments/"+ data["document_id"]
    #     if not os.path.exists(path):
    #         os.makedirs(path)
            
    #     writer = pd.ExcelWriter(path+'/parsedData.xls', engine='xlsxwriter')
    #     doc_df.to_excel(writer, sheet_name='Data 1', index=False)
    #     prod_df.to_excel(writer, sheet_name='Product Table', index=False)
    #     writer.save()
        
    #     writer = pd.ExcelWriter(path+'/productMissMatch.xls', engine='xlsxwriter')
    #     prod_match_df.to_excel(writer, sheet_name='Product Table', index=False)
    #     writer.save()
        
        
    #     domain_name = "https://site4.anantdemo.com"
    #     #domain_name = "https://fd10549899a2.ngrok.io"
    #     domain = domain_name + "/download/?type=parsed&doc_id=" + data["document_id"] 
    #     prod_match_uri =  domain_name + "/download/?type=missmatch&doc_id=" + data["document_id"] 
    #     return resp_text + "\n\n You can download the miss matched products by clicking on the link below! \n"+ prod_match_uri +"\n\n You can download the parsed data by clicking on the link below! \n" + domain
    
    # def main(self, gearman_worker, gearman_job):
    #     user_data = {}
    #     diaglog_data = {}
    #     stockist_data = {}
    #     clear_context = False
    #     return_data = {
    #         "context_id": "",
    #         "state": ""
    #         }
    #     # context_id = ""
    #     resp_text = ""
    #     table_data = []
    #     response_dict = {
    #         "channel": "",
    #         "response_text": ""
    #     }
    #     processed_data = {}
    #     context_id2 = ""
    #     print ("===in main===")
    #     data = json.loads(gearman_job.data)

    #     # print ("data", data)
    #     user_data, collected_data, context_id  = self.getUserData(data.get("document_id",""),data.get('senderPhoneNumber',''))
    #     if user_data.get("collected_data",{}) and user_data.get("collected_data",{}).get("stockist",""):
    #         stockist_name = user_data.get("collected_data",{}).get("stockist","")  
    #         stockist_data = self.getStockistData(stockist_name[0])
            
            
    #     if data.get("file_data",[]):
    #         # upload_details = self.upload_documents(data.get("file_data",[]))
    #         document_id = str(uuid.uuid4())
    #         destination_blob_name = "uploaded_files/{}/{}".format(document_id, data["file_data"]["caption"])
            
    #         if not os.path.exists("uploaded_files/" + document_id):
    #             os.makedirs("uploaded_files/" +document_id)
    #         r = requests.get(data["file_data"]["url"], allow_redirects=True)
    #         open(destination_blob_name, 'wb').write(r.content)
            
    #         if destination_blob_name.lower().endswith((".csv", ".xls", ".xlsx")):
    #             ext = os.path.splitext(destination_blob_name)[-1].lower()
    #             table_data = self.excel_extractor(destination_blob_name, ext , stockist_data)
    #         elif destination_blob_name.lower().endswith(".pdf"):
    #             table_data = self.upload_blob_process_data('doc_etraction', destination_blob_name, destination_blob_name,stockist_name)
            
    #         data["product_table"] = table_data
    #         data["document_id"] = document_id
                    
            
    #     if "document_id" in data:
    #         processed_data = self.process_parsed_data(data, stockist_data)
    #     if data.get('senderPhoneNumber','') and data.get('app_name',''):
    #         user_data['senderPhoneNumber'] = data.get('senderPhoneNumber','')
    #         user_data['app_name'] = data.get('app_name','')

    #     if data.get("text",""):
    #         # diaglog_data = self.callDialogFlow(data["text"])
    #         diaglog_data = data.get("diaglog_data", {})
            
    #         if diaglog_data["intent"] == "detect_numbers":
    #             options_asked = user_data.get("options_asked", {})
    #             temp = []
    #             for num in  diaglog_data["detected_params"].get("numbers",[]):
    #                 if str(num) in options_asked:
    #                     temp.append(options_asked[str(num)])
    #             if user_data["last_state"] == "ask_stockist":
    #                 collected_data["stockist"] = temp
    #             elif user_data["last_state"] == "product_resolution":
    #                 collected_data["product_names"] = temp
        
    #         if diaglog_data["intent"] == "detect_stockist":
    #             if user_data["last_state"] == "ask_stockist" and diaglog_data["detected_params"].get("stockist",[]):
    #                 print("select api calls")
    #                 collected_data["stockist"] = diaglog_data["detected_params"].get("stockist",[])

    #         if diaglog_data["intent"] == "Default Welcome Intent" or not collected_data.get("stockist",[]):
    #             # pdb.set_trace()
    #             #set context
    #             numbered_options = {}
    #             resp_text = "Hi, let me know for which stockist would you like to scan the document ? \n"
    #             stockist_names = ""
            
    #             add_count = 1
    #             for i in sorted(self.stockist_list):
    #                 temp =  i.title()
    #                 stockist_names +=  str(add_count) + ". " + re.sub("\s\s+", " ", temp) + " \n"
    #                 numbered_options[str(add_count)] = i 
    #                 add_count += 1
    #             resp_text += stockist_names
    #             return_data["state"] = "ask_stockist"
    #             return_data["context_id"] = context_id
    #             user_data["last_state"] = return_data["state"]
    #             user_data["options_asked"] = numbered_options
    #                 # self.context_dict["test_123"] = user_data
    #         elif len(collected_data.get("stockist",[])) > 1:
    #             resp_text = "Hey, I detected multiple stockist and since I an still learning, can you help me for which stockist you want to scan a document? \n"
    #             doc_list = ""
    #             numbered_options = {}
    #             add_count = 1
    #             for i in collected_data.get("stockist", []):
    #                 temp =  i.title()
    #                 doc_list +=  str(add_count) + ". " + re.sub("\s\s+", " ", temp) + " \n"
    #                 numbered_options[str(add_count)] = i 
    #                 add_count += 1
    #             resp_text += doc_list
    #             return_data["state"] = "ask_stockist"
    #             return_data["context_id"] = context_id
    #             user_data["last_state"] = return_data["state"]
    #             user_data["options_asked"] = numbered_options
    #             collected_data["stockist"] =[]
    #         elif len(collected_data.get("product_names",[])) > 1:
    #             product_details = user_data["prod"]
    #             resp_text = "Hey, I detected multiple products names and since I an still learning, please select the correct product for *" + product_details.get("item","") + "* \n" 
    #             prod_list = ""
    #             numbered_options = {}
    #             add_count = 1
    #             for i in collected_data.get("product_names", []):
    #                 prod_list +=  str(add_count) + ". " + i + " \n"
    #                 numbered_options[str(add_count)] = i 
    #                 add_count += 1
    #             resp_text += prod_list
    #             return_data["state"] = "product_resolution"
    #             return_data["context_id"] = context_id
    #             user_data["last_state"] = return_data["state"]
    #             user_data["options_asked"] = numbered_options
    #             collected_data["product_names"] =[]
    #         elif len(collected_data.get("product_names",[])) == 1:
    #             print( "====in selecting other products===")
    #             # pdb.set_trace()
    #             res_prod_list = user_data.get("res_prod_list",[])
    #             resolved_items = user_data.get("resolved_items",[])
    #             product_details = user_data.get("prod",{})
    #             resolved_name = collected_data.get("product_names",[])[0]
    #             product_details["resolved_name"] = resolved_name
    #             stockist_name = user_data.get("collected_data",{}).get("stockist","")  
    #             stockist_data = self.getStockistData(stockist_name[0])
    #             if product_details["item"] not in stockist_data:
    #                 stockist_data[product_details["item"]] = resolved_name
    #                 self.updateStockistData(stockist_data)
    #             res_prod_list.append(product_details)
    #             resolved_items.append(product_details.get("item"))
    #             processed_data = user_data.get("processed_data",{}) 
    #             product_table = processed_data["product_table"]
    #             no_prod = True
    #             for prod in product_table:
    #                 if prod.get("item") not in resolved_items and prod.get("ask_user",[]):
    #                     no_prod = False
    #                     prod_data = prod.get("ask_user",[])
    #                     op_count = 1
    #                     options_asked = {}
    #                     resp_text = "Please select the correct option for *" + prod.get("item","") + "* \n"
    #                     for val in  prod_data:
    #                         resp_text += str(op_count) + ". " + val + "\n"
    #                         options_asked[op_count] = val
    #                         op_count += 1
    #                     resp_text += "\n_Please select the number against the options_"
    #                     user_data["resolved_items"] = resolved_items
    #                     return_data["state"] = "product_resolution"
    #                     return_data["context_id"] = context_id
    #                     user_data["last_state"] = return_data["state"]
    #                     user_data["prod"] = prod
    #                     user_data["options_asked"] = options_asked
    #                     break
    #             user_data["res_prod_list"] = res_prod_list
    #             user_data["resolved_items"] = resolved_items
    #             if no_prod:
    #                 resp_text = "Thank you for helping me map the products"
    #                 return_data["state"] = "mapping_completed"
    #                 return_data["context_id"] = context_id
    #                 user_data["last_state"] = return_data["state"]
    #                 resp_text = self.completeMapping(user_data["processed_data"], resp_text)
    #         else:
    #             resp_text = "Please upload the document for " + " ".join(collected_data.get("stockist",[]))
    #             stockist_name = user_data.get("collected_data",{}).get("stockist",[])
    #             stockist_data = self.getStockistData(stockist_name[0])
    #             stockist_data["stockist"] = stockist_name[0]
    #             self.updateStockistData(stockist_data)
    #             print("upload doc here")
    #     # elif data.get("file_data",[]):
    #     #     upload_details = self.upload_documents(data.get("file_data",[]))
    #     #     print("call doc parser", json.dumps(data.get("file_data",[]), indent =4))
    #     #     print ("uploaded details", json.dumps(upload_details, indent =4))
    #     #     context_id2 = upload_details["id"] + "_doc_parser"
    #     #     user_data["pre_context_id"] = context_id
    #     #     user_data["doc_context_id"] = context_id2
    #     #     resp_text = "Thank you for uploading, your document will be scanned and updated into the database! \n Here is your reference id: *" + upload_details["id"] + "*"
    #     #     return_data["state"] = "doc_uploaded"
    #     #     return_data["context_id"] = context_id2
    #     #     user_data["last_state"] = return_data["state"]
    #     #     user_data["options_asked"] = {}
    #     elif processed_data:
    #         print("===in processed_data===")
    #         user_data["processed_data"] = processed_data
    #         document_id = processed_data.get("document_id","")
    #         resolved_items = user_data.get("resolved_items", [])
    #         # print("processed_data", json.dumps(processed_data,indent =2))
    #         product_table = processed_data["product_table"]
            
    #         resp_text = "Document parsing has been completed for the reference id: *" + document_id
            
    #         if processed_data.get("difference_count") == 0:
    #             return_data["state"] = "mapping_completed"
    #             return_data["context_id"] = context_id
    #             user_data["last_state"] = return_data["state"]
    #             resp_text = self.completeMapping(user_data["processed_data"], resp_text)
    #         elif processed_data.get("difference_count") > 0:
    #             portal_url ="https://144.76.139.247/AIPL_whatsapp/whatsapp_bot_demo/doc_par.php?docid=" + document_id
    #             resp_text += "*\n\nFound *" + str(processed_data.get("difference_count")) + "* mismatch with the product names.\n\nPlease click the link "+ portal_url +" to resolved the issue."
    #             return_data["state"] = "url_sent"
    #             return_data["context_id"] = context_id
    #             user_data["last_state"] = return_data["state"]
    #             resp_text = self.completeMapping(user_data["processed_data"], resp_text)
    #         else:
    #             for prod in product_table:
    #                 if prod.get("item") not in resolved_items and prod.get("ask_user",[]):
    #                     prod_data = prod.get("ask_user",[])
    #                     op_count = 1
    #                     options_asked = {}
    #                     resp_text += "*\n\nSince I am still learning, please help me with selecting the correct product name to map it with the master table in the database. \n\nPlease select the correct option for *" + prod.get("item","") + "* \n"
    #                     for val in  prod_data:
    #                         resp_text += str(op_count) + ". " + val + "\n"
    #                         options_asked[op_count] = val
    #                         op_count += 1
    #                     resp_text += "\n_Please select the number against the options_"
    #                     user_data["resolved_items"] = resolved_items
    #                     return_data["state"] = "product_resolution"
    #                     return_data["context_id"] = context_id
    #                     user_data["last_state"] = return_data["state"]
    #                     user_data["prod"] = prod
    #                     user_data["options_asked"] = options_asked
    #                     break
                
    #     print ("response ")
        
    #     # clear_context = True
        
    #     user_data["collected_data"] = collected_data    
    #     response_dict["response_text"] = resp_text
    #     response_dict["return_data"] = return_data
    #     response_dict["collected_data"] = collected_data
    #     response_dict["senderPhoneNumber"] = user_data['senderPhoneNumber']
    #     response_dict["app_name"] = user_data['app_name']
        
    #     if clear_context:
    #         self.redis_db.delete(context_id)
    #     else:
    #         self.redis_db.setex(context_id, 360000, json.dumps(user_data))
        
    #     if context_id2 :
    #         self.redis_db.setex(context_id2, 360000, json.dumps(user_data))
            
    #     print ("======\n\n")
    #     print (json.dumps(response_dict, indent = 4))
    #     print ("hereeeeee")
        
    #    return json.dumps(response_dict)
    
    
if __name__ == '__main__':
    print ("working...")
    obj = chatworker()
    table_df = obj.excel_extractor("./sample/SRIKAAR.xls", ".xls", {"stockist"  : "SRIKAAR PHARMACY"})
    # print(table_data)
    # obj.gm_worker.work()
    
