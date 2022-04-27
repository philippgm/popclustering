# from google.cloud import bigquery, storage
import json

QUERY_CREDENTIALS = 'standard-premium-testing-af822aafc611.json'
INSERT_CREDENTIALS = 'standard-premium-testing-f7a510f5ee7d.json'
DATASET_ID = 'speedchecker_probes'
STORAGE_BUCKET_NAME = 'standard-premium-testing-storage'
STORAGE_BUCKET_URI = 'gs://standard-premium-testing-storage/'
TARGET_FILENAME = 'tier1-prefix-dns-tests'
TARGET_TABLE = 'Tier1PrefixReverseDNS_Test'

# from Todd's code bulk_measurements.py
def convertToBigQueryJSONFormat(data):
    dataString = ""
    for d in data:
        d = json.dumps(d).replace('\n','')
        dataString += (d + '\n')
    return dataString
  
def sendToCloudStorage(data, fileName):
    attempt = 0
    try:
        attempt += 1
        storage_client = storage.Client.from_service_account_json(INSERT_CREDENTIALS)
        bucket = storage_client.get_bucket(STORAGE_BUCKET_NAME)
        blob = bucket.blob(fileName)
        print("Uploading results to Cloud Storage (try #{}): {}".format(attempt, blob))
        blob.upload_from_string(data)
        print('Successfully uploaded ({} attempts) {}.'.format(attempt, blob))
    except Exception as err:
        print("Attempt {} failed to upload {} due to {}:{}".format(attempt, blob, Exception, err))
  
def sendToBigQuery(dataSet, targetTable, gcFile):
    print ("Transferring from Storage to BigQuery")
    
    client = bigquery.Client.from_service_account_json(INSERT_CREDENTIALS)
    dataset_ref = client.dataset(DATASET_ID)
    table_ref = dataset_ref.table(targetTable)

    try:
        previous_rows = client.get_table(table_ref).num_rows
    except:
        # The table does not exist so we will have to create it
        previous_rows = 0
    job_config = bigquery.LoadJobConfig()
    job_config.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    uri = STORAGE_BUCKET_URI + gcFile
    if previous_rows > 0:
        print("Appending {} to table {}".format(gcFile, targetTable))
        job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
        load_job = client.load_table_from_uri(uri, table_ref,
                job_config=job_config)  # API request
        
        assert load_job.job_type == 'load'
        load_job.result()  # Waits for table load to complete.
        assert load_job.state == 'DONE'
        print("Append successful for {} data to BigQuery table {}".format(
            gcFile, targetTable))
    else:
        # We really don't want to do this...
        print("Creating table {}".format(targetTable))
        job_config.autodetect = True
        load_job = client.load_table_from_uri(
                uri,
                dataset_ref.table(targetTable),
                job_config=job_config)  # API request
        assert load_job.job_type == 'load'
        load_job.result()  # Waits for table load to complete.
        assert load_job.state == 'DONE'
        print("Successfully created {} and transferred {} data to BigQuery".format(
            targetTable, gcFile))