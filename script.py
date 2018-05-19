import boto3
import json


from botocore.vendored import requests

def send(ResponseURL, StackId, physicalResourceId, RequestId, LogicalResourceId):
    responseUrl = ResponseURL

    print(responseUrl)

    responseBody = {}
    responseBody['Status'] = "SUCCESS"
    responseBody['Reason'] = 'See the details in CloudWatch Log Stream: ' 
    responseBody['PhysicalResourceId'] = physicalResourceId 
    responseBody['StackId'] = StackId
    responseBody['RequestId'] = RequestId
    responseBody['LogicalResourceId'] = LogicalResourceId
    json_responseBody = json.dumps(responseBody)

    print("Response body:\n" + json_responseBody)

    headers = {
        'content-type' : '',
        'content-length' : str(len(json_responseBody))
    }

    try:
        response = requests.put(responseUrl,
                                data=json_responseBody,
                                headers=headers)
        print("Status code: " + response.reason)
    except Exception as e:
        print("send(..) failed executing requests.put(..): " + str(e))

def handler(event, context):
  sdb = boto3.client('sdb')
  if "ResourceProperties" in event: #inital CF request
    sts = boto3.client('sts')


    try:
      sdb.create_domain(
        DomainName='cf-hit'
      )
    except:
      pass

    creds = sts.assume_role(
    RoleArn=event["ResourceProperties"]["Role"],
    RoleSessionName='CFTurk'
    )
    
    client = boto3.client('mturk', endpoint_url=event["ResourceProperties"]["TurkEndpoint"], region_name='us-east-1')
    response = client.create_hit(
        MaxAssignments=1,
        AutoApprovalDelayInSeconds=10,
        LifetimeInSeconds=36000,
        AssignmentDurationInSeconds=3600,
        Reward=event["ResourceProperties"]["Reward"],
        Title='AWS Build Enviroment',
        Keywords='string',
        Description='Build an AWS enviroment. You will experience with AWS services to perform this task',
        Question="""<QuestionForm xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2005-10-01/QuestionForm.xsd">
      <Overview>
        <Title>AWS Env Build</Title>
        <Text>
          You are helping to build an AWS Enviroment with the following specifications:
        </Text>
        <Text>
          """ + event["ResourceProperties"]["Description"] +"""
        </Text>
        <Text>
          Your temporary creds are:
          AccessKeyId:""" + creds["Credentials"]["AccessKeyId"]+ """
          SecretAccessKey:""" + creds["Credentials"]["SecretAccessKey"]+ """
          SessionToken:""" + creds["Credentials"]["SessionToken"]+ """
        </Text>
      </Overview>
      <Question>
        <QuestionIdentifier></QuestionIdentifier>
        <DisplayName>Completeion</DisplayName>
        <IsRequired>true</IsRequired>
        <QuestionContent>
          <Text>
            Have you completed building the enviroment listed? (Do not finish this HIT until the answer below is done)
          </Text>
        </QuestionContent>
    <AnswerSpecification>
          <SelectionAnswer>
            <StyleSuggestion>radiobutton</StyleSuggestion>
            <Selections>
              <Selection>
                <SelectionIdentifier>done</SelectionIdentifier>
                <Text>Done</Text>
              </Selection>
              <Selection>
                <SelectionIdentifier>notdone</SelectionIdentifier>
                <Text>Not Done</Text>
              </Selection>
            </Selections>
          </SelectionAnswer>
        </AnswerSpecification>
      </Question>
    </QuestionForm>
        """
    )
    sdb.put_attributes(
      DomainName="cf-hit",
      ItemName=response["HIT"]["HITId"],
      Attributes=[
        {
          "Name": "ResponseURL",
          "Value": event["ResponseURL"],
          "Replace": True
        },
        {
          "Name": "StackId",
          "Value": event["StackId"],
          "Replace": True
        },
        {
          "Name": "RequestId",
          "Value": event["RequestId"],
          "Replace": True
        },
        {
          "Name": "LogicalResourceId",
          "Value": event["LogicalResourceId"],
          "Replace": True
        }
      ]


    )
    client.update_notification_settings(HITTypeId=response["HIT"]["HITTypeId"],Notification={
      "Destination": event["ResourceProperties"]["SNS"],
      "Transport": "SNS",
      "Version": "2006-05-05",
      "EventTypes":["AssignmentSubmitted"]
    }, Active=True)


    #update_notification_settings
  else: #SNS from turk
    data = json.loads(event["Records"][0]["Sns"]["Message"])
    hitId = data["Events"][0]["HITId"]
    response = sdb.get_attributes(
      DomainName="cf-hit",
      ItemName=hitId,
      AttributeNames=[
        "ResponseURL",
        "StackId",
        "RequestId",
        "LogicalResourceId"
      ]
    )
    attrs = {v['Name']: v['Value'] for v in response['Attributes']}
    attrs["physicalResourceId"] = hitId
    send(**attrs)