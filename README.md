# GoogleSheets to BigQuery -- Cloud Function ETL
Automate Google Forms Reponses on Google Sheets to be Imported in Bigquery & Automate Building Parameterized Views.

Business Process

Different Google Forms are being reponded back. These Responses are being stored in Google Cloud Sheet on Google Drive. All new responses (identified interm of records by modified date column) with the googlel cloud sheet should be imported in Bigquery(And GCS as a Backup). 

Based-on data imported Views should be created to be used in the reporting. Views are dependent on 2 Lookups (Present as Google Sheets as well) which are used in data joins which is used for data validations.

Goals

    1.	Automatically capture New Google Sheets Records and Store it to BQ
    2.	Maintain a Metadata Store for the Files Captured
    3.	Automatically Cross Check/Validate new data schema
    4.	Create BQ Datasets, Tables & Views
    5.	Look Files Auto Refresh

![image](https://user-images.githubusercontent.com/26026302/181238664-2224677d-3285-4879-ba27-6e3ab11954cf.png)
