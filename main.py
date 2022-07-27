import google.auth
import os.path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime
from google.cloud import storage
import configparser
from google.cloud import bigquery
import pygsheets
import json
import re

def confReader():
    try:
        print("In confReader")
        config = configparser.ConfigParser()
        config.read(os.path.dirname(__file__) + '/properties.conf')
        configs=config._sections
        return configs
    except Exception as e:
        print("write_file Error: "+str(e) )

def colGSheetConfReader():
    try:
        spreadsheet_id=conf["GSHEET"]["colschema_sheetid"]
        sheet = GSheet_client.open_by_key(spreadsheet_id)
        wks = sheet.worksheet_by_title(conf["GSHEET"]["colschema_wksname"])
        read_df = wks.get_as_df()
        return read_df["COL_NAME"].to_list()
    except Exception as e:
        print("colGSheetConfReader Error: "+str(e)) 

drive_credentials, drive_project_id = google.auth.default(scopes = ['https://www.googleapis.com/auth/drive.metadata.readonly'])
GSheet_credentials, GSheet_project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])

GSheet_client = pygsheets.authorize(custom_credentials=GSheet_credentials)
storage_client = storage.Client()
bq_client = bigquery.Client()

conf=confReader()

def GDrive_List():
     try:
          print("GDrive_List() -- Started") 
          drive_service = build('drive', 'v3', credentials=drive_credentials)
          page_token = None
          drive_items = []
          while True:                    
               mod_date='2021-02-22T12:00:00'

               print(os.environ.get("LAST_RUN"))
               if os.environ.get("LAST_RUN"):
                   mod_date=os.environ.get("LAST_RUN")
                   os.environ["LAST_RUN"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
               else:
                   mod_date = '2021-02-22T12:00:00'
                   os.environ["LAST_RUN"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

               query="modifiedTime > '"+str(mod_date)+"' and mimeType = 'application/vnd.google-apps.spreadsheet' and name contains '"+str(conf["GSHEET"]["worksheet_matching_word"])+"'"
               drive_results = drive_service.files().list(q=query,
                                             spaces='drive',
                                             fields='nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)',
                                             pageToken=page_token).execute()
               drive_items.extend(drive_results.get('files', []))
               if not drive_items:
                    print('No files found.')
                    return
               page_token = drive_results.get('nextPageToken', None)
               if page_token is None:
                    break    
          print("GDrive_List() -- Ended") 
          return drive_items 
     except HttpError as error:
          print(f'GDrive_List() Error: {error}')

def write_file(path,filename,data):
     try:
         print("write_file() -- Started")
         bucket = storage_client.get_bucket(conf["STORAGE"]["bucket_name"])
         
         path=str(path)+str(filename)
         
         blob = bucket.blob(path)
         with blob.open(mode='w') as f:
              f.write(str(data))
         print("write_file() -- Ended")     
         return path
     except Exception as e:
         print("write_file Error: "+str(e) )
            
def GCSMeta(filename,mod_date,data):
     try:
         print("GCSMeta() -- Started")         
         bucket = storage_client.bucket(conf["STORAGE"]["bucket_name"])
         iterator = bucket.list_blobs(delimiter="/")
         response = iterator._get_next_page_response(   )     
         dataExistanceFlag=False

         filename = filename.replace(" ","_")
         
         if 'prefixes' in list(response.keys()):
             dir = filename+"/"               
             if dir in response['prefixes']:               
                 dataExistanceFlag=True
             else: 
                 dataExistanceFlag=False
         else:
             dataExistanceFlag=False

         filepath=str(filename)+"/"
         file_mod=str(filename)+"_"+str(mod_date)
             
         path = write_file(filepath,file_mod,data)
         print("GCSMeta() -- Ended")
         return dataExistanceFlag, path         
     except Exception as e:
         print("GCSMeta Error: "+str(e))
         

def BQMeta(path):
    try:
        print("BQMeta() -- Started")
        job_config = bigquery.LoadJobConfig(autodetect=True, source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON)
        uri = "gs://"+str(conf["STORAGE"]["bucket_name"])+"/"+str(path)
        load_job = bq_client.load_table_from_uri(uri, conf["BQ"]["meta_table_id"], job_config=job_config)
        load_job.result()
        print("BQMeta() -- Ended")
    except Exception as e:
        print("BQMeta Error: "+str(e))

def ReadGSheet(spreadsheet_id):
    try:
        print("ReadGSheet() -- Started")
        sheet = GSheet_client.open_by_key(spreadsheet_id)
        wks = sheet.worksheet_by_title(conf["GSHEET"]["worksheet_name"])
        read_df = wks.get_as_df()
        print("ReadGSheet() -- Ended")
        return read_df
    except Exception as e:
        print("ReadGSheet Error: "+str(e))    

def BQDataset_Create(dataset_id):
    try:
        print("BQDataset_Create() -- Started")
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = conf["BQ"]["data_dataset_location"]
        dataset = bq_client.create_dataset(dataset, timeout=30)  # Make an API request.
        print("BQDataset_Create() -- Ended")
    except Exception as e:
        print("BQDataset_Create Error: "+str(e))         

def BQTable_Create(table_id):
    try:
        print("BQTable_Create() -- Started")
        table = bigquery.Table(table_id, schema=None)
        table = bq_client.create_table(table)
        print("BQTable_Create() -- Ended")
    except Exception as e:
        print("BQTable_Create Error: "+str(e))                     

def BQTable_Insert(table_id,data):
    try:
        print("BQTable_Insert() -- Started")
        data.columns = data.columns.str.replace(' ', '_',regex = True)
        data.columns = data.columns.str.replace('’', '_',regex = True)
        data.columns = data.columns.str.replace(r'[\\\|,\-+!~@#$%^&*()={}\[\]:;<.>?\/\'"]', '_',regex = True)
        data.columns = data.columns.str.replace(r'(_)+', '_',regex = True)
        colL=[]
        for col in list(data.columns):
            colL.append(col[:300])
        data.columns = colL
                
        job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
        job = bq_client.load_table_from_dataframe(data, table_id, job_config=job_config)  # Make an API request.
        job.result()  
        print("BQTable_Insert() -- Ended")
    except Exception as e:
        print("BQTable_Insert Error: "+str(e))                     

def BQView_1_Create(view_id,source_id):
    try:
        print("BQView_1_Create() -- Started")
        view = bigquery.Table(view_id)
        ## Important ## view.view_query = <VIEW QUERY>
        view = bq_client.create_table(view)
        print("BQView_1_Create() -- Ended")
    except Exception as e:
        print("BQView_1_Create Error: "+str(e))                     

def BQView_2_Create(view_id,source_id):
    try:
        print("BQView_2_Create() -- Started")        
        view = bigquery.Table(view_id)
        ## Important ## view.view_query = <VIEW QUERY>
        view = bq_client.create_table(view)
        print("BQView_2_Create() -- Ended")
    except Exception as e:
        print("BQView_2_Create Error: "+str(e))                     


def BG_Jobs_Group(filename,data,itemExistanceFlag):
    try:
        print("BG_Jobs_Group() -- Started")
        
        filename = filename.replace(" ","_")
        filename = re.sub(r'[\\\|,\-+!~@#$%^&*()={}\[\]:;<.>?\/\'"]', '_', filename)
        dataset_id = format(bq_client.project)+"."+filename
        table_id = dataset_id+"."+str(conf["GSHEET"]["worksheet_name"])
        view1_id = dataset_id+".internal_view_1"
        view2_id = dataset_id+".internal_view_2"
        source_id = table_id

        if not itemExistanceFlag:
            BQDataset_Create(dataset_id)
            BQTable_Create(table_id)
            
        BQTable_Insert(table_id,data) 
        if not itemExistanceFlag:
            BQView_1_Create(view1_id,source_id)
            BQView_2_Create(view2_id,view1_id) 
        print("BG_Jobs_Group() -- Ended")                  
    except Exception as e:
        print("BG_Jobs_Group Error: "+str(e))                 


def MAIN(event, context):
    try:
        print("MAIN() -- Started")
        col_conf_list = colGSheetConfReader()
        drive_items = GDrive_List()
        if drive_items:
            for item in drive_items:
                df=ReadGSheet(item["id"])
                len_col_conf_list=len(col_conf_list)
                if len_col_conf_list == len(list(df.columns)):
                    flag="True"
                    for col in list(df.columns):
                        if col in col_conf_list:
                            pass
                        else:
                            flag="Flase"
                            print(f"""MAIN() -- Column [ {col} ] of Dataset [ {item["name"]} ] is not matching the default schema""")
                    if flag == "True":
                        itemExistanceFlag, path=GCSMeta(item["name"],item["modifiedTime"],item)
                        BQMeta(path)
                        BG_Jobs_Group(item["name"],df,itemExistanceFlag)
                    else:
                        print(f"""MAIN() -- Dataset [ {item["name"]} ] coulmns not matching the default schema, Skipping Dataset... .""")
                else:
                    print(f"""MAIN() -- Columns Count of Dataset [ {item["name"]} ] is [ {len(list(df.columns))} ] not matching the default schema column count of [ {len_col_conf_list} ] column""")
        else:
            print("MAIN() -- Exiting ...")
            return
        print("MAIN() -- Ended")
    except Exception as e:
        print("Main Error: "+str(e))