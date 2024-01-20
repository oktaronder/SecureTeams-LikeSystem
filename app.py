from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad, unpad
import binascii
import os

app = Flask(__name__)
app.secret_key = '1110'

# MongoDB Atlas bağlantısı
app.config["MONGO_URI"] = "mongodb+srv://oktaronder:Oktar2001@cluster0.7vfrotb.mongodb.net/chat_app?retryWrites=true&w=majority"
mongo = PyMongo(app)

# DES için sabit anahtar ve IV
DES_KEY = b'8bytekey'
DES_IV = b'12345678'

def des_encrypt(plain_text):
    des = DES.new(DES_KEY, DES.MODE_CBC, DES_IV)
    padded_text = pad(plain_text.encode('utf-8'), DES.block_size)
    encrypted_text = des.encrypt(padded_text)
    return binascii.hexlify(encrypted_text).decode('utf-8')

def des_decrypt(cipher_text):
    des = DES.new(DES_KEY, DES.MODE_CBC, DES_IV)
    decrypted_padded_text = des.decrypt(binascii.unhexlify(cipher_text))
    decrypted_text = unpad(decrypted_padded_text, DES.block_size)
    return decrypted_text.decode('utf-8')

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        user = users.find_one({'email': request.form['email']})
        if user and des_decrypt(user['password']) == request.form['password']:
            session['username'] = user['username']
            session['email'] = user['email']
            session['role'] = user['role']

            # Rol kontrolü
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'teacher' or user['role'] == 'student':
                return redirect(url_for('dashboard'))
        else:
            flash('Giriş bilgileriniz yanlış. Lütfen tekrar deneyiniz.', 'nologin')

    return render_template('login.html')

@app.route('/logout')
def logout():
    # Kullanıcı oturum bilgilerini temizle
    session.clear()
    return redirect(url_for('login'))


@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        users = mongo.db.users
        existing_user = users.find_one({'email': request.form['email']})
        if existing_user:
            flash('Bu e-posta adresi zaten kayıtlı.', 'emailre')
            return redirect(url_for('add_user'))
        encrypted_password = des_encrypt(request.form['password'])
        users.insert_one({
            'username': request.form['username'],
            'email': request.form['email'],
            'password': encrypted_password,
            'role': request.form.get('role', 'student')
        })
        flash('New user sign in was successful', 'addeduser')
        # Aynı sayfada kal
        return redirect(url_for('add_user'))
    return render_template('add_user.html')


@app.route('/user/<user_id>')
def user_profile(user_id):
    # Here you should retrieve the user information from your database based on the user_id
    # and pass it to the template.
    user = {}  # This should be replaced with actual user retrieval logic
    return render_template('user_profile.html', user=user)


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        if session['role'] == 'admin':
            # Yönetici paneline yönlendir
            return redirect(url_for('admin_dashboard'))

        elif session['role'] == 'teacher':
            # Öğretmen için tüm grupları al
            groups_cursor = mongo.db.groups.find({})
        else:
            # Öğrenci için sadece üyesi olduğu grupları al
            groups_cursor = mongo.db.groups.find({'members': session['email']})

        # Cursor'ı liste haline getir ve her grup için logo kontrolü yap
        groups = []
        for group in groups_cursor:
            # Grubun logosu yoksa varsayılan bir resim URL'si kullan
            group['logo_url'] = group.get('logo_url', url_for('static', filename='images/default_group.png'))
            groups.append(group)

        # Kullanıcı bilgilerini ekleyin
        user_info = mongo.db.users.find_one({'username': session['username']})
        session['user_image'] = user_info.get('profile_pic', url_for('static', filename='images/default_user.png'))

        return render_template('dashboard.html', groups=groups)
    else:
        return redirect(url_for('login'))

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' in session and session['role'] == 'admin':
        # Admin panelini oluşturmak için gerekli kodları burada ekleyin.
        return render_template('admin_dashboard.html')
    else:
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('login'))

@app.route('/create_update_des_key', methods=['GET', 'POST'])
def create_update_des_key():
    if 'username' in session and session['role'] == 'admin':
        if request.method == 'POST':
            # DES anahtarını oluştur veya güncelle
            # Gerekli kodları burada ekleyin
            flash('DES Secret Key successfully created/updated.', 'success')
            return redirect(url_for('admin_dashboard'))
        return render_template('create_update_des_key.html')
    else:
        flash('Bu işlemi yapmaya yetkiniz yok.', 'danger')
        return redirect(url_for('login'))

@app.route('/update_des_key')
def update_des_key():
    if 'username' in session and session['role'] == 'admin':
        return render_template('update_des_key.html')
    else:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))




@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if 'username' in session and session['role'] == 'teacher':
        if request.method == 'POST':
            group_name = request.form['group_name']
            group_description = request.form.get('group_description', '')

            mongo.db.groups.insert_one({
                'name': group_name,
                'description': group_description,
                'members': [],
                'channels': ['General', 'Labs']
            })
            flash('Group successfully created.', 'group_message')
            return redirect(url_for('dashboard'))
        return render_template('create_group.html')
    else:
        flash('Bu sayfaya erişmek için yetkiniz yok.', 'danger')
        return redirect(url_for('login'))

@app.route('/delete_group/<group_id>', methods=['POST'])
def delete_group(group_id):
    if 'username' in session and session['role'] == 'teacher':
        mongo.db.groups.delete_one({'_id': ObjectId(group_id)})
        flash('Group successfully deleted.', 'success')
    else:
        flash('You do not have permission to perform this action.', 'error')
    return redirect(url_for('dashboard'))

@app.route('/group/<group_id>')
def group(group_id):
    if 'username' in session:
        group = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
        if group and (session['email'] in group['members'] or session['role'] == 'teacher'):
            channels = group.get('channels', [])
            return render_template('group.html', group=group, channels=channels)
        else:
            flash('Bu gruba erişim yetkiniz yok.', 'danger')
            return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/group/<group_id>/add_channel', methods=['GET', 'POST'])
def add_channel(group_id):
    if 'username' in session and (session['role'] == 'teacher' or session['role'] == 'student'):
        if request.method == 'POST':
            channel_name = request.form.get('channel_name')
            mongo.db.groups.update_one(
                {'_id': ObjectId(group_id)},
                {'$push': {'channels': channel_name}}
            )
            flash('Channel successfully added.', 'channel_message')
            return redirect(url_for('group', group_id=group_id))
        return render_template('add_channel.html', group_id=group_id)
    else:
        flash('Bu işlemi yapmaya yetkiniz yok.', 'danger')
        return redirect(url_for('login'))

@app.route('/delete_channel/<group_id>/<channel_name>', methods=['POST'])
def delete_channel(group_id, channel_name):
    if 'username' in session and (session['role'] == 'teacher' or session['role'] == 'student'):
        mongo.db.groups.update_one(
            {'_id': ObjectId(group_id)},
            {'$pull': {'channels': channel_name}}
        )
        flash('Channel successfully deleted.', 'channel_message')
    else:
        flash('You do not have permission to delete this channel.', 'error')
    return redirect(url_for('group', group_id=group_id))




@app.route('/group/<group_id>/add_member', methods=['GET', 'POST'])
def add_member(group_id):
    if 'username' in session and session['role'] == 'teacher':
        if request.method == 'POST':
            member_email = request.form['member_email']
            existing_member = mongo.db.users.find_one({'email': member_email})
            if not existing_member:
                flash('Eklenmek istenen kullanıcı sistemde bulunamadı.', 'member_eror')
                return redirect(url_for('add_member', group_id=group_id))
            mongo.db.groups.update_one(
                {'_id': ObjectId(group_id)},
                {'$push': {'members': member_email}}
            )
            flash('Member successfully added.', 'member_message')
            return redirect(url_for('group', group_id=group_id))
        return render_template('add_member.html', group_id=group_id)
    else:
        flash('Üye eklemek için yetkiniz yok.', 'danger')
        return redirect(url_for('login'))


@app.route('/group/<group_id>/channel/<channel_name>')
def channel(group_id, channel_name):
    if 'username' in session:
        group = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
        if group and channel_name in group['channels']:
            # Mesajları MongoDB'den çek
            messages = list(mongo.db.messages.find({
                'group_id': ObjectId(group_id),
                'channel_name': channel_name
            }))

            # Mesajları şifresini çöz ve kullanıcı bilgileri ile birlikte liste haline getir
            decrypted_messages = []
            for message in messages:
                user_info = mongo.db.users.find_one({'username': message['user']})
                user_image = user_info.get('profile_pic', url_for('static', filename='images/default_user.png'))
                decrypted_messages.append({
                    'author': message['user'],
                    'text': des_decrypt(message['text']),
                    'user_image': user_image,
                    'timestamp': message.get('timestamp')  # Varsa zaman damgası bilgisi de eklenebilir
                })

            return render_template('channel.html', group_id=group_id, channel_name=channel_name, messages=decrypted_messages)
        else:
            flash('Bu kanala erişim yetkiniz yok veya kanal bulunamadı.', 'danger')
            return redirect(url_for('group', group_id=group_id))
    else:
        flash('Bu işlemi yapabilmek için giriş yapmalısınız.', 'danger')
        return redirect(url_for('login'))



@app.route('/group/<group_id>/channel/<channel_name>/send_message', methods=['POST'])
def send_message(group_id, channel_name):
    if 'username' in session:
        message_text = request.form['message']
        if message_text:
            try:
                encrypted_message = des_encrypt(message_text)
                mongo.db.messages.insert_one({
                    'user': session['username'],
                    'group_id': ObjectId(group_id),
                    'channel_name': channel_name,
                    'text': encrypted_message
                })
                flash('Mesaj başarıyla gönderildi.', 'success')
            except ValueError as e:
                flash('Mesaj şifrelenirken bir hata oluştu: {}'.format(e), 'danger')
        else:
            flash('Mesajın içeriği boş olamaz.', 'danger')
        return redirect(url_for('channel', group_id=group_id, channel_name=channel_name))
    else:
        flash('Mesaj göndermek için giriş yapmalısınız.', 'danger')
        return redirect(url_for('login'))

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/user/<user_id>/update_profile_pic', methods=['POST'])
def update_profile_pic(user_id):
    if 'profile_pic' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['profile_pic']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Veritabanında kullanıcı profil fotoğrafını güncelle
        users = mongo.db.users
        users.update_one({'_id': ObjectId(user_id)}, {'$set': {'profile_pic': filepath}})

        flash('Profile picture updated successfully.')
        return redirect(url_for('user_profile', user_id=user_id))

    flash('Invalid file type.')
    return redirect(request.url)

@app.route('/user/<user_id>')
def view_user_profile(user_id):
    users = mongo.db.users
    user = users.find_one({'_id': ObjectId(user_id)})
    if not user:
        flash('User not found.')
        return redirect(url_for('dashboard'))
    return render_template('user_profile.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)

