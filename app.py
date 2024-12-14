from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Настройки подключения к базе данных
def get_db_connection():
    conn = psycopg2.connect(
        dbname="library", user="postgres", password="Yashkino311", host="localhost", port="5432"
    )
    return conn

# Функция для проверки значения на корректность
def validate_data(columns, values, table_name):
    errors = []

    for column, value in zip(columns, values):
        if value == '':
            # Устанавливаем значение по умолчанию для `quantity` в таблице `books`
            if column == 'quantity' and table_name == 'books':
                values[8] = 1
                break
            else:
                errors.append(f"Поле '{column}' не может быть пустым.")

        # Пример валидации для числовых столбцов
        if (column == 'age' or column == 'year' or column == 'quantity' or (column[len(column)-2] == 'i' and column[len(column)-1] == 'd')) and not value.isdigit():
            errors.append(f"Поле '{column}' должно быть числом.")

        if (column == 'age' and table_name == 'employees') and (int(value) < 18 or int(value) > 100):
            errors.append(f"Поле age должен быть больше 18 и меньше 100 лет.")

        if (column == 'age' and table_name == 'readers') and (int(value) < 16 or int(value) > 100):
            errors.append(f"Поле age должен быть больше 16 и меньше 100 лет.")

        # Проверка уникальности значения phone
        if column == 'phone':
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {column} = %s", (value,))
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            if count > 0:
                errors.append(
                f"Поле phone должно быть уникальным. Значение {value} уже существует в таблице {table_name}.")

    return errors

# Функция для получения списка столбцов таблицы
def get_columns(table_name):
    conn = get_db_connection()
    cur = conn.cursor()
    # SQL-запрос для получения списка столбцов
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s;
    """, (table_name,))

    columns = cur.fetchall()
    cur.close()
    conn.close()
    # Возвращаем список столбцов
    return [col[0] for col in columns]

# Функция для получения данных из таблицы, извлекает все строки
def get_table_data(table_name, filter_query=None, sort_by=None):
    conn = get_db_connection()
    cur = conn.cursor()
    sql = f"SELECT * FROM {table_name}"

    if filter_query:
        sql += f" WHERE {filter_query}"

    if sort_by:
        sql += f" ORDER BY {sort_by}"

    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# Функция для получения одной записи по ее id
def get_record_by_id(table_name, record_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name} WHERE id = %s", (record_id,))
    record = cur.fetchone()
    cur.close()
    conn.close()

    # Создаем список кортежей (имя столбца, значение)
    return list(zip(get_columns(table_name), record)) if record else []

# Обновляет данные в записи по ее id
def update_record(table_name, record_id, updated_values):
    conn = get_db_connection()
    cur = conn.cursor()
    set_clause = ", ".join([f"{col} = %s" for col in updated_values.keys()])
    values = list(updated_values.values()) + [record_id]
    cur.execute(f"UPDATE {table_name} SET {set_clause} WHERE id = %s", values)
    conn.commit()
    cur.close()
    conn.close()

# Функция для добавления новой строки в таблицу
def add_row_to_table(table_name, values):
    conn = get_db_connection()
    cur = conn.cursor()
    columns = get_columns(table_name)
    placeholders = ", ".join(["%s"] * len(columns))  # создаем placeholders для столбцов с обычным вводом
    insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

    cur.execute(insert_query, values)
    conn.commit()
    cur.close()
    conn.close()

# Cписок внешних ключей
def get_foreign_keys(table_name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            kcu.column_name, 
            ccu.table_name AS referenced_table, 
            ccu.column_name AS referenced_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s;
    """, (table_name,))
    foreign_keys = cur.fetchall()
    cur.close()
    conn.close()

    # Возвращаем список внешних ключей: [(column_name, referenced_table, referenced_column), ...]
    return [
        {"column": fk[0], "referenced_table": fk[1], "referenced_column": fk[2]}
        for fk in foreign_keys
    ]

# Значения внешних ключей для таблицы и столбца в ней
def get_foreign_key_values(referenced_table, referenced_column):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT {referenced_column} FROM {referenced_table}")
    values = cur.fetchall()
    cur.close()
    conn.close()
    return [value[0] for value in values]  # Возвращаем список уникальных значений

# Получить следующий возможный id для таблицы
def get_next_id(table_name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT MAX(id) FROM {table_name}")
    max_id = cur.fetchone()[0]
    cur.close()
    conn.close()
    return (max_id or 0) + 1  # Если таблица пуста, начать с 1

def add_row_to_table_with_return(table_name, values):
    conn = get_db_connection()
    cur = conn.cursor()
    columns = ", ".join(values.keys())
    placeholders = ", ".join(["%s"] * len(values))
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) RETURNING id"
    cur.execute(sql, list(values.values()))
    conn.commit()
    new_id = cur.fetchone()[0]
    cur.close()
    conn.close()
    return new_id

# Страница для отображения данных из выбранной таблицы
@app.route('/table/<table_name>', methods=['GET', 'POST'])
def table_view(table_name):
    filter_query = request.form.get('filter') # Получаем фильтр, если он задан
    sort_by = request.form.get('sort') # Получаем поле для сортировки, если оно задано
    rows = get_table_data(table_name, filter_query, sort_by)
    columns = get_columns(table_name)
    search_column = request.form.get('search_column', '')

    # Получение списка таблиц
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
    i = 0
    table_list = []
    view_list = []
    for table in cur.fetchall():
        if table[0].count('_') == 0:
            table_list.append(table[0])
        else:
            view_list.append(table[0])

    cur.close()
    conn.close()

    # Переход на страницу с конкретной таблицей
    return render_template('table_view.html', table_name=table_name, rows=rows, columns=columns, search_column=search_column, table_list=table_list, view_list=view_list)

# Страница для отображения данных из выбранного представления
@app.route('/view/<view_name>')
def view_view(view_name):
    # Подключение к базе данных
    conn = get_db_connection()
    cur = conn.cursor()

    # Получаем данные из представления
    cur.execute(f"SELECT * FROM {view_name};")
    rows = cur.fetchall()

    # Получаем имена столбцов для отображения в таблице
    columns = [desc[0] for desc in cur.description]

    cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
    i = 0
    table_list = []
    view_list = []
    for table in cur.fetchall():
        if table[0].count('_') == 0:
            table_list.append(table[0])
        else:
            view_list.append(table[0])

    conn.close()

    # Отправляем данные в шаблон
    return render_template('view_view.html', view_name=view_name, columns=columns, rows=rows, table_list=table_list, view_list=view_list)

# Страница добавления записи в таблицу
@app.route('/table/<table_name>/add', methods=['GET', 'POST'])
def add_record(table_name):
    columns = get_columns(table_name)
    foreign_keys = get_foreign_keys(table_name)  # Получаем внешние ключи таблицы

    # Значения внешних ключей для выбора в выпадающих списках
    fk_values = {
        fk['column']: get_foreign_key_values(fk['referenced_table'], fk['referenced_column'])
        for fk in foreign_keys
    }

    # Следующее значение для id
    next_id = get_next_id(table_name)

    if request.method == 'POST':
        values = []
        for column in columns:
            if column in fk_values:
                values.append(request.form.get(column))  # Значение из выпадающего списка
            elif column == 'id':
                values.append(request.form.get(column))  # Пользовательский ввод для id
            else:
                values.append(request.form.get(column))  # Обычный ввод

        # Валидация данных с учетом внешних ключей
        errors = validate_data(columns, values, table_name)
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template(
                'add_record.html',
                table_name=table_name,
                columns=columns,
                fk_values=fk_values,
                next_id=next_id
            )

        # Добавляем запись в таблицу
        add_row_to_table(table_name, values)
        return redirect(url_for('table_view', table_name=table_name))

    return render_template(
        'add_record.html',
        table_name=table_name,
        columns=columns,
        fk_values=fk_values,
        next_id=next_id
    )

# Страница добавления записи в таблицу loans
@app.route('/table/loans/add', methods=['GET', 'POST'])
def add_loans():
    columns = get_columns('loans')
    foreign_keys = get_foreign_keys('loans')

    # Значения внешних ключей
    fk_values = {
        fk['column']: get_foreign_key_values(fk['referenced_table'], fk['referenced_column'])
        for fk in foreign_keys
    }

    if request.method == 'POST':
        # Получаем идентификатор читателя
        reader_id = request.form.get('reader_id')
        if not reader_id:
            flash("Reader ID is required.", "error")
            return render_template(
                'add_loans.html',
                table_name='loans',
                fk_values=fk_values,
            )

        # Получаем данные для каждой записи
        book_ids = request.form.getlist('book_id[]')
        library_ids = request.form.getlist('library_id[]')
        employee_ids = request.form.getlist('employee_id[]')
        issue_dates = request.form.getlist('issue_date[]')
        return_dates = request.form.getlist('return_date[]')

        # Генерируем следующий доступный id
        current_id = get_next_id('loans')

        # Создаем записи
        for book_id, library_id, employee_id, issue_date, return_date in zip(
                book_ids, library_ids, employee_ids, issue_dates, return_dates):
            values = {
                'id': current_id,
                'reader_id': reader_id,
                'book_id': book_id,
                'library_id': library_id,
                'employee_id': employee_id,
                'issue_date': issue_date,
                'return_date': return_date,
            }
            add_row_to_table_with_return('loans', values)
            current_id += 1  # Увеличиваем ID для следующей записи

        flash("Записи успешно добавлены!", "success")
        return redirect(url_for('table_view', table_name='loans'))

    return render_template(
        'add_loans.html',
        table_name='loans',
        fk_values=fk_values,
    )

# Страница добавления записей в таблицы readers и loans
@app.route('/add_reader_with_loans', methods=['GET', 'POST'])
def add_reader_with_loans():
    # Значения внешних ключей для выпадающих списков
    fk_values = {
        'book_id': get_foreign_key_values('books', 'id'),
        'library_id': get_foreign_key_values('libraries', 'id'),
        'employee_id': get_foreign_key_values('employees', 'id')
    }
    if request.method == 'POST':
        # Сначала добавляем запись в таблицу readers
        reader_values = {
            'id': get_next_id('readers'),
            'surname': request.form['surname'],
            'name': request.form['name'],
            'patronymic': request.form['patronymic'],
            'address': request.form['address'],
            'phone': request.form['phone'],
            'age': request.form['age']
        }

        # Проверяем данные для readers
        errors = validate_data(list(reader_values.keys()), list(map(str, reader_values.values())), 'readers')
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('add_reader_with_loans.html', fk_values=fk_values)

        # Сохраняем нового читателя
        reader_id = add_row_to_table_with_return('readers', reader_values)

        # Затем добавляем записи в таблицу loans
        book_ids = request.form.getlist('book_id[]')
        library_ids = request.form.getlist('library_id[]')
        employee_ids = request.form.getlist('employee_id[]')
        issue_dates = request.form.getlist('issue_date[]')
        return_dates = request.form.getlist('return_date[]')

        # Генерируем следующий доступный id для loans
        loan_id = get_next_id('loans')

        for book_id, library_id, employee_id, issue_date, return_date in zip(
                book_ids, library_ids, employee_ids, issue_dates, return_dates):
            loan_values = {
                'id': str(loan_id),
                'reader_id': str(reader_id),
                'book_id': str(book_id),
                'library_id': str(library_id),
                'employee_id': str(employee_id),
                'issue_date': issue_date,
                'return_date': return_date,
            }
            errors = validate_data(list(loan_values.keys()), list(loan_values.values()), 'loans')
            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('add_reader_with_loans.html', fk_values=fk_values)

            add_row_to_table_with_return('loans', loan_values)
            loan_id += 1

        flash('Читатель и записи о займах успешно добавлены!', 'success')
        return redirect(url_for('table_view', table_name='readers'))

    return render_template('add_reader_with_loans.html', fk_values=fk_values)

# Страница для редактирования записи по ее id
@app.route('/table/<table_name>/edit/<int:id>', methods=['GET', 'POST'])
def edit_record(table_name, id):
    columns = get_columns(table_name)  # Получаем столбцы таблицы
    record = get_record_by_id(table_name, id)  # Получаем текущие данные записи

    if request.method == 'POST':
        updated_values = {}
        for idx, column in enumerate(columns):
            #updated_values[column] = request.form[column]  # Собираем обновленные данные
            if column == 'quantity' and table_name == 'books':
                updated_values[column] = request.form.get(column) or '1'  # По умолчанию `1`, если не указано
            else:
                updated_values[column] = request.form.get(column)  # Собираем обновленные данные

        # Валидация данных
        errors = validate_data(columns, list(updated_values.values()), table_name)
        if errors:
            for error in errors:
                flash(error, 'error')  # Отображаем ошибки пользователю
            return render_template(
                'edit_record.html',
                table_name=table_name,
                columns=columns,
                record=record
            )

        # Если ошибок нет, обновляем запись
        update_record(table_name, id, updated_values)
        return redirect(url_for('table_view', table_name=table_name))

    return render_template('edit_record.html', table_name=table_name, columns=columns, record=record)

# Удаляет записи из таблицы по id при этом остается на той же странице table_view
@app.route('/delete/<table_name>/<int:id>')
def delete_record(table_name, id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table_name} WHERE id = {id}")
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('table_view', table_name=table_name))

# Страница для поиска записей по выбранному столбцу и конкретному значению
@app.route('/table/<table_name>/search', methods=['GET', 'POST'])
def search_records(table_name):
    columns = get_columns(table_name)
    search_results = []
    search_value = ''
    search_column = ''

    if request.method == 'POST':
        search_value = request.form.get('search_value', '').strip()
        search_column = request.form.get('search_column', '')

        if search_column and search_value:
            conn = get_db_connection()
            cur = conn.cursor()
            query = f"SELECT * FROM {table_name} WHERE {search_column}::TEXT ILIKE %s"
            cur.execute(query, (f"%{search_value}%",))
            search_results = cur.fetchall()
            cur.close()
            conn.close()

    return render_template(
        'search_results.html',
        table_name=table_name,
        columns=columns,
        search_results=search_results,
        search_value=search_value,
        search_column=search_column,
    )

# Главная страница для перехода к таблицам
@app.route('/')
def index():
    # Подключение к базе данных
    conn = get_db_connection()
    cur = conn.cursor()

    # Получаем список всех таблиц
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    table_list = [table[0] for table in cur.fetchall() if table[0].count('_') == 0]
    print(13570)
    print(table_list)

    # Получаем список всех представлений
    cur.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'public';")
    view_list = [view[0] for view in cur.fetchall()]
    print(view_list)
    conn.close()

    # Отправляем данные в шаблон
    return render_template('index.html', table_list=table_list, view_list=view_list)

if __name__ == '__main__':
    app.run(debug=True)