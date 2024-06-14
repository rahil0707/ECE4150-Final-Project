#!flask/bin/python
import sys, os
sys.path.append(os.path.abspath(os.path.join('..', 'utils')))
from env import AWS_ACCESS_KEY, AWS_SECRET_ACCESS_KEY, AWS_REGION, CANVASPROJECT_S3_BUCKET_NAME, DYNAMODB_TABLE, DYNAMODB_TABLE_USER
from flask import Flask, jsonify, abort, request, make_response, url_for, session
from flask import render_template, redirect
import time
import exifread
import json
import uuid
import boto3  
from boto3.dynamodb.conditions import Key, Attr
import pymysql.cursors
from datetime import datetime, timedelta
import pytz

"""
    INSERT NEW LIBRARIES HERE (IF NEEDED)
"""
import bcrypt
from botocore.exceptions import ClientError
from itsdangerous import URLSafeTimedSerializer


"""
We just applied LAB2 NoSQL part to the CANVAS PROJECT
We implement CANVAS Homepage
 - We implement user register function
 - We implement user confirm email function
 - We implement registering courses function
 - We implement uploading class notes function
 - We implement editing the class notes function
 - We implement deleting the class notes function
 - We implement deleting the user function
"""

# Class -> play role as Album
# Lecture -> play role as Photos

app = Flask(__name__, static_url_path="")
app.secret_key = "secretece"

dynamodb = boto3.resource('dynamodb', aws_access_key_id=AWS_ACCESS_KEY,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=AWS_REGION)

# Dynamodb table for the uploaded files 
table = dynamodb.Table(DYNAMODB_TABLE)

# Dynamodb table for the user
usertable = dynamodb.Table(DYNAMODB_TABLE_USER)

UPLOAD_FOLDER = os.path.join(app.root_path,'static','media')
# Extend the file extensions (We added the pdf, xlsx, doc, docx including the image files)
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls', 'doc', 'docx'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def getExifData(path_name):
    f = open(path_name, 'rb')
    tags = exifread.process_file(f)
    ExifData={}
    for tag in tags.keys():
        if tag not in ('JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote'):
            key="%s"%(tag)
            val="%s"%(tags[tag])
            ExifData[key]=val
    return ExifData

def s3uploading(filename, filenameWithPath, uploadType="photos"):
    s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=AWS_REGION)
                       
    bucket = CANVASPROJECT_S3_BUCKET_NAME
    path_filename = uploadType + "/" + filename

    s3.upload_file(filenameWithPath, bucket, path_filename)  
    s3.put_object_acl(ACL='public-read', Bucket=bucket, Key=path_filename)
    return f'''http://{CANVASPROJECT_S3_BUCKET_NAME}.s3.amazonaws.com/{path_filename}'''


@app.route('/signup', methods=['GET', 'POST'])
def sign_up():
    """ Sign up Page.

    get:
        description: Endpoint to return signup page.
        responses: displays the signup screen prompting information to user

    post: 
        description: Endpoint to send user signup information.
        responses: Returns user to log-in page.
    """
    if request.method == 'POST':
        userID = request.form['username']
        name = request.form['name']
        password = request.form['password']
        email = request.form['email']

        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('UTF-8'), salt)
        hased_indb = hashed.decode('UTF-8')

        createdAtlocalTime = datetime.now().astimezone()
        createdAtUTCTime = createdAtlocalTime.astimezone(pytz.utc)

        usertable.put_item(
            Item={
                "userID": str(userID),
                "name": name,
                "password": hased_indb,
                "emailID": str(email),
            }
        )

        return redirect('/confirmationemail')
    else:
        return render_template('signup.html')


@app.route('/confirmation1email/<string:token>')
def confirm1(token):
    """ Handling the confirmation token.
    """
    return redirect('/login')

@app.route('/confirmationemail', methods=['GET','POST'])
def confirmation_email():
    """confirmation email page.

    get:
        description: Endpoint to return log-in page.
        responses: send out a token to verify the user

    post:
        description: Endpoint to return log-in page.
        responses: Returns the log-in page.
    """

    #creating a token
    email = "mhussain43@gatech.edu"
    serializer = URLSafeTimedSerializer("LtvZOn6shelXcu6usujHtaX2dFofWljhLm6z6W59")
    token = serializer.dumps(email, salt = "LtvZOn6shelXcu6usujHtaX2dFofWljhLm6z6W59")

    print(token)
    try:
        email = serializer.loads(
            token,
            salt = "LtvZOn6shelXcu6usujHtaX2dFofWljhLm6z6W59",
            max_age = 600
        )
        print(token)
    except Exception as e:
        print("expired token")
        return render_template('signup.html')

    #sending an email
    ses = boto3.client('ses',
        region_name = AWS_REGION,
        aws_access_key_id = AWS_ACCESS_KEY,
        aws_secret_access_key = AWS_SECRET_ACCESS_KEY)
    # We can edit the SENDER and RECEIVER email address
    SENDER = 'mhussain43@gatech.edu'
    RECEIVER = 'bsh.pat77@gmail.com'
    try:
        ses.send_email(
                Destination = {
                    'ToAddresses': [RECEIVER],
                },
                Message = {
                    'Body': {
                        'Text': {

                            'Data': '''\
                                http://ec2-3-95-154-181.compute-1.amazonaws.com:5000/confirmation1email/{t}
                            This is an email from AWS SES
                            If you want to register the canvas homepage, please click the above link to confirm.\
                                '''.format(t=token)
                        }
                    },
                    'Subject': {
                        'Data': 'Hi, I\'m sending this email from AWS SES'
                    },
                },
                Source =  SENDER
            )
    except ClientError as e:
        print("Error!")
    else:
        print("Email sent!")
    return redirect('/login') #go to login page when verified


@app.route('/login', methods = ['GET', 'POST'])
def log_in():
    """log in page.

    get:
        description: Endpoint to return log-in page.
        responses: allow user to log in if information matches

    post:
        description: Endpoint to return the homepage.
        responses: Returns the homepage.
    """
    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        emailTable = usertable.scan(FilterExpression = Attr('email').eq(email))['Items']
        if not (emailTable):
            print("emailTable Error")
            return render_template('login.html')


        pwTable = usertable.scan(FilterExpression = Attr('email').eq(email))['Items']
        print(pwTable)
        if not (pwTable):
            print("pwTable Error")
            return render_template('login.html')


        pwdCorrect = bcrypt.checkpw(password.encode('UTF-8'), (pwTable[0])["password"].encode('UTF-8'))
        
        if email == (emailTable[0])["email"] and pwdCorrect:  
            session['username'] = (emailTable[0])["userID"]
            session.permanenent = True
            app.permanenent_session_lifetime = timedelta(minutes=5)
            return render_template('index.html')
        else:
            print("Wrong! Try again")
            return redirect('/login')
        
    else:
        print("Reached the end")
        return render_template('login.html')

@app.route('/cancelaccount', methods = ['GET'])
def cancel_account():
    """Cancel a user account.

    get:
        description: Remove all the albums created by a user when the user cancels the account.
        responses: Returns the sign-up page since this user was canceled.
    """
    userID = session['username']
    response = table.scan(FilterExpression = Attr('userID').eq(userID))
    items = response['Items']
    for item in items:
        delete_class(item['classID'])
        table.delete_item(
        Key={
        'classID': item['classID'],
        'lectureID': item['lectureID']
        }    
            )
    return redirect('/')

@app.route('/class/<string:classID>/delete', methods=['GET'])
def delete_class(classID):
    """ Delete the whole album

    get:
        description: Endpoint to delete all photos in an album.
        responses: Returns the empty homepage.
    """
    response = table.scan(FilterExpression=Attr('classID').eq(classID) & Attr('lectureID').ne('thumbnail'))
    items = response['Items']
    for item in items:
        table.delete_item(
            Key={
            'classID': item['classID'],
            'lectureID': item['lectureID']
            }
        )
    return redirect('/class/' + classID)

@app.route('/class/<string:classID>/<string:lectureID>/delete', methods = ['GET'])
def delete_lecture(classID, lectureID):
    """ Delete a photo

    get:
        description: Endpoint to delete a photo.
        responses: Returns the empty homepage.
    """
    table.delete_item(
        Key = {
            'classID' : classID,
            'lectureID' : lectureID
        }
    )
    return redirect('/class/' + classID)

@app.route('/class/<string:classID>/<string:lectureID>/update', methods = ['GET', 'POST'])
def update_lecture(classID, lectureID):
    """ Update a photo

    get:
        description: Endpoint to return a page to be updated.
        responses: Returns all the fields to be updated.
    post:
        description: Endpoint to display the updated information.
        responses: Returns the updated album information page.

    """
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        tags = request.form['tags']
        updatedAtlocalTime = datetime.now().astimezone()
        updatedAtUTCTime = updatedAtlocalTime.astimezone(pytz.utc)
        table.update_item(
            Key = {
                'classID' : classID,
                'lectureID' : lectureID
            },
            UpdateExpression = "set title =:title, description =:description, tags =:tags, updatedAt =:updatedAt",
            ExpressionAttributeValues = {
                ':title': title,
                ':description': description,
                ':tags': tags,
                ':updatedAt': updatedAtUTCTime.strftime("%Y-%m-%d %H:%M:%S")

            },
            ReturnValues = "UPDATED_NEW"
        )
        return redirect('/class/' + classID + '/lecture/' + lectureID)
    else:
        return render_template('updateLecture.html', lectureID=lectureID, classID=classID)

"""
"""

@app.errorhandler(400)
def bad_request(error):
    """ 400 page route.

    get:
        description: Endpoint to return a bad request 400 page.
        responses: Returns 400 object.
    """
    return make_response(jsonify({'error': 'Bad request'}), 400)



@app.errorhandler(404)
def not_found(error):
    """ 404 page route.

    get:
        description: Endpoint to return a not found 404 page.
        responses: Returns 404 object.
    """
    return make_response(jsonify({'error': 'Not found'}), 404)



@app.route('/', methods=['GET'])
def home_page():
    """ Home page route.

    get:
        description: Endpoint to return home page.
        responses: Returns all the albums.
    """
    response = table.scan(FilterExpression=Attr('lectureID').eq("thumbnail"))
    results = response['Items']

    if 'username' in session:
        response = table.scan(FilterExpression = Attr('lectureID').eq('thumbnail'))
        results = response['Items']

        if len(results) > 0:
            for index, value in enumerate(results):
                createdAt = datetime.strptime(str(results[index]['createdAt']), "%Y-%m-%d %H:%M:%S")
                createdAt_UTC = pytz.timezone("UTC").localize(createdAt)
                results[index]['createdAt'] = createdAt_UTC.astimezone(pytz.timezone("US/Eastern")).strftime("%B %d, %Y")

        return render_template('index.html', classes=results)
    else:
        return redirect('login')



@app.route('/createClass', methods=['GET', 'POST'])
def add_class():
    """ Create new album route.

    get:
        description: Endpoint to return form to create a new album.
        responses: Returns all the fields needed to store new album.

    post:
        description: Endpoint to send new album.
        responses: Returns user to home page.
    """
    if request.method == 'POST':
        uploadedFileURL=''
        file = request.files['imagefile']
        name = request.form['name']
        description = request.form['description']

        if file and allowed_file(file.filename):
            classID = uuid.uuid4()
            
            filename = file.filename
            filenameWithPath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filenameWithPath)
            
            uploadedFileURL = s3uploading(str(classID), filenameWithPath, "thumbnails");

            createdAtlocalTime = datetime.now().astimezone()
            createdAtUTCTime = createdAtlocalTime.astimezone(pytz.utc)

            print(session, '\n\n')
            table.put_item(
                Item={
                    "classID": str(classID),
                    "lectureID": "thumbnail",
                    "name": name,
                    "description": description,
                    "thumbnailURL": uploadedFileURL,
                    "userID": session['username'],
                    "createdAt": createdAtUTCTime.strftime("%Y-%m-%d %H:%M:%S")
                }
            )

        return redirect('/')
    else:
        return render_template('classForm.html')



@app.route('/class/<string:classID>', methods=['GET'])
def view_lectures(classID):
    """ Album page route.

    get:
        description: Endpoint to return an album.
        responses: Returns all the photos of a particular album.
    """
    classResponse = table.query(KeyConditionExpression=Key('classID').eq(classID) & Key('lectureID').eq('thumbnail'))
    classMeta = classResponse['Items']

    response = table.scan(FilterExpression=Attr('classID').eq(classID) & Attr('lectureID').ne('thumbnail'))
    items = response['Items']

    return render_template('viewClass.html', lectures=items, classID=classID, className=classMeta[0]['name'])



@app.route('/class/<string:classID>/addLecture', methods=['GET', 'POST'])
def add_lecture(classID):
    """ Create new photo under album route.

    get:
        description: Endpoint to return form to create a new photo.
        responses: Returns all the fields needed to store a new photo.

    post:
        description: Endpoint to send new photo.
        responses: Returns user to album page.
    """
    if request.method == 'POST':    
        uploadedFileURL=''
        file = request.files['imagefile']
        title = request.form['title']
        description = request.form['description']
        tags = request.form['tags']
        if file and allowed_file(file.filename):
            lectureID = uuid.uuid4()
            filename = file.filename
            filenameWithPath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filenameWithPath)            
            
            uploadedFileURL = s3uploading(filename, filenameWithPath)
            
            ExifData=getExifData(filenameWithPath)
            ExifDataStr = json.dumps(ExifData)

            createdAtlocalTime = datetime.now().astimezone()
            updatedAtlocalTime = datetime.now().astimezone()

            createdAtUTCTime = createdAtlocalTime.astimezone(pytz.utc)
            updatedAtUTCTime = updatedAtlocalTime.astimezone(pytz.utc)

            table.put_item(
                Item={
                    "classID": str(classID),
                    "lectureID": str(lectureID),
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "lectureURL": uploadedFileURL,
                    "EXIF": ExifDataStr,
                    "createdAt": createdAtUTCTime.strftime("%Y-%m-%d %H:%M:%S"),
                    "updatedAt": updatedAtUTCTime.strftime("%Y-%m-%d %H:%M:%S")
                }
            )

        return redirect(f'''/class/{classID}''')

    else:

        classResponse = table.query(KeyConditionExpression=Key('classID').eq(classID) & Key('lectureID').eq('thumbnail'))
        classMeta = classResponse['Items']

        return render_template('lectureForm.html', classID=classID, className=classMeta[0]['name'])



@app.route('/class/<string:classID>/lecture/<string:lectureID>', methods=['GET'])
def view_lecture(classID, lectureID):
    """ photo page route.

    get:
        description: Endpoint to return a photo.
        responses: Returns a photo from a particular album.
    """ 
    classResponse = table.query(KeyConditionExpression=Key('classID').eq(classID) & Key('lectureID').eq('thumbnail'))
    classMeta = classResponse['Items']

    response = table.query( KeyConditionExpression=Key('classID').eq(classID) & Key('lectureID').eq(lectureID))
    results = response['Items']
    print(results,'\n\n')

    if len(results) > 0:
        lecture={}
        lecture['lectureID'] = results[0]['lectureID']
        lecture['title'] = results[0]['title']
        lecture['description'] = results[0]['description']
        lecture['tags'] = results[0]['tags']
        lecture['lectureURL'] = results[0]['lectureURL']
        lecture['EXIF']=json.loads(results[0]['EXIF'])

        createdAt = datetime.strptime(str(results[0]['createdAt']), "%Y-%m-%d %H:%M:%S")
        updatedAt = datetime.strptime(str(results[0]['updatedAt']), "%Y-%m-%d %H:%M:%S")

        createdAt_UTC = pytz.timezone("UTC").localize(createdAt)
        updatedAt_UTC = pytz.timezone("UTC").localize(updatedAt)

        lecture['createdAt']=createdAt_UTC.astimezone(pytz.timezone("US/Eastern")).strftime("%B %d, %Y")
        lecture['updatedAt']=updatedAt_UTC.astimezone(pytz.timezone("US/Eastern")).strftime("%B %d, %Y")
        
        tags=lecture['tags'].split(',')
        exifdata=lecture['EXIF']
        
        return render_template('lecturedetail.html', lecture=lecture, tags=tags, exifdata=exifdata, classID=classID, className=classMeta[0]['name'])
    else:
        return render_template('lecturedetail.html', lecture={}, tags=[], exifdata={}, classID=classID, className="")



@app.route('/class/search', methods=['GET'])
def search_class_page():
    """ search album page route.

    get:
        description: Endpoint to return all the matching albums.
        responses: Returns all the albums based on a particular query.
    """ 
    query = request.args.get('query', None)    

    response = table.scan(FilterExpression=Attr('name').contains(query) | Attr('description').contains(query))
    results = response['Items']

    items=[]
    for item in results:
        if item['lectureID'] == 'thumbnail':
            classes={}
            classes['classID'] = item['classID']
            classes['name'] = item['name']
            classes['description'] = item['description']
            classes['thumbnailURL'] = item['thumbnailURL']
            items.append(classes)

    return render_template('searchClass.html', classes=items, searchquery=query)



@app.route('/class/<string:classID>/search', methods=['GET'])
def search_lecture_page(classID):
    """ search photo page route.

    get:
        description: Endpoint to return all the matching photos.
        responses: Returns all the photos from an album based on a particular query.
    """ 
    query = request.args.get('query', None)    

    response = table.scan(FilterExpression=Attr('title').contains(query) | Attr('description').contains(query) | Attr('tags').contains(query) | Attr('EXIF').contains(query))
    results = response['Items']

    items=[]
    for item in results:
        if item['lectureID'] != 'thumbnail' and item['classID'] == classID:
            lecture={}
            lecture['lectureID'] = item['lectureID']
            lecture['classID'] = item['classID']
            lecture['title'] = item['title']
            lecture['description'] = item['description']
            lecture['lectureURL'] = item['lectureURL']
            items.append(lecture)

    return render_template('searchLecture.html', lectures=items, searchquery=query, classID=classID)



if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
