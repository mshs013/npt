### Django Commands with Examples

1. **startproject <projectname>**
    - **Description**: Creates a new Django project directory structure.
    - **Example**: `django-admin startproject myproject`
    - **Documentation**: Initializes the settings for a new Django project with a default structure. This is the first command when starting a new Django app.

2. **startapp <appname>**
    - **Description**: Creates a new Django app within the project.
    - **Example**: `python manage.py startapp blog`
    - **Documentation**: Generates the necessary files for a new app like models, views, and admin configurations.

3. **makemigrations [appname]**
    - **Description**: Creates migrations based on model changes.
    - **Example**: `python manage.py makemigrations blog`
    - **Documentation**: Detects changes in models and prepares migration files for database schema updates.

4. **migrate [appname]**
    - **Description**: Applies migrations to the database.
    - **Example**: `python manage.py migrate blog`
    - **Documentation**: Syncs the database schema with your models and applied migrations.

5. **sqlmigrate <appname> <migration_number>**
    - **Description**: Displays the SQL statements for a migration.
    - **Example**: `python manage.py sqlmigrate blog 0001`
    - **Documentation**: Shows the SQL commands that will be run by a specific migration.

6. **showmigrations [appname]**
    - **Description**: Lists migrations and their status.
    - **Example**: `python manage.py showmigrations blog`
    - **Documentation**: Displays a list of all available migrations and indicates which have been applied.

7. **createsuperuser**
    - **Description**: Creates a superuser for Django’s admin.
    - **Example**: `python manage.py createsuperuser`
    - **Documentation**: A user with full permissions can be created through an interactive prompt.

8. **changepassword <username>**
    - **Description**: Changes a user’s password.
    - **Example**: `python manage.py changepassword admin`
    - **Documentation**: Allows resetting the password for any user.

9. **shell**
    - **Description**: Opens a Python shell with Django context loaded.
    - **Example**: `python manage.py shell`
    - **Documentation**: Useful for testing and interacting with your Django project programmatically.

10. **runserver [port]**
    - **Description**: Runs the development server.
    - **Example**: `python manage.py runserver 8080`
    - **Documentation**: Starts a local web server for testing the project.

11. **runserver_plus [port]**
    - **Description**: Enhanced version of runserver (requires `django-extensions`).
    - **Example**: `python manage.py runserver_plus 8080`
    - **Documentation**: Offers more debugging features and tools for running the server.

12. **test [appname]**
    - **Description**: Runs the test suite.
    - **Example**: `python manage.py test blog`
    - **Documentation**: Executes the unit tests for your Django project or specific apps.

13. **testserver <fixture>**
    - **Description**: Runs a server with fixture data loaded.
    - **Example**: `python manage.py testserver data.json`
    - **Documentation**: Useful for testing specific datasets on a temporary server.

14. **collectstatic**
    - **Description**: Collects static files into `STATIC_ROOT`.
    - **Example**: `python manage.py collectstatic`
    - **Documentation**: Gathers static files from your apps and third-party packages into a single directory for production.

15. **findstatic <file>**
    - **Description**: Locates a static file.
    - **Example**: `python manage.py findstatic style.css`
    - **Documentation**: Finds a static file in your `STATICFILES_DIRS` and app directories.

16. **loaddata <fixture>**
    - **Description**: Loads data from fixture files into the database.
    - **Example**: `python manage.py loaddata initial_data.json`
    - **Documentation**: Populates the database with initial data or data from fixtures (JSON, XML, YAML).

17. **dumpdata [appname] --output=<filename>**
    - **Description**: Outputs the contents of the database as a fixture.
    - **Example**: `python manage.py dumpdata blog --output=data.json`
    - **Documentation**: Dumps the contents of a model or app into a fixture file.

18. **check**
    - **Description**: Checks for project configuration issues.
    - **Example**: `python manage.py check`
    - **Documentation**: Runs system checks for potential errors and misconfigurations in your project.

19. **diffsettings**
    - **Description**: Displays differences between your settings and Django defaults.
    - **Example**: `python manage.py diffsettings`
    - **Documentation**: Helps to identify settings you’ve customized compared to Django’s default settings.

20. **dbshell**
    - **Description**: Opens the database shell.
    - **Example**: `python manage.py dbshell`
    - **Documentation**: Gives you direct access to your database via the command line.

21. **flush**
    - **Description**: Removes all data from the database but keeps the schema intact.
    - **Example**: `python manage.py flush`
    - **Documentation**: Clears all the data from the database without removing the structure (tables).

22. **sqlflush**
    - **Description**: Outputs SQL statements required to flush the database.
    - **Example**: `python manage.py sqlflush`
    - **Documentation**: Useful for understanding how Django manages data removal.

23. **inspectdb**
    - **Description**: Generates models based on an existing database schema.
    - **Example**: `python manage.py inspectdb`
    - **Documentation**: Generates Python code for models based on the current database tables.

24. **migrate [appname] [migration_name]**
    - **Description**: Applies a specific migration.
    - **Example**: `python manage.py migrate blog 0002`
    - **Documentation**: Runs a specific migration to update the database.

25. **runserver_plus**
    - **Description**: Runs the development server with advanced debugging.
    - **Example**: `python manage.py runserver_plus`
    - **Documentation**: A version of runserver with more tools and features (requires `django-extensions`).

26. **shell_plus**
    - **Description**: An enhanced shell that auto-imports models (requires `django-extensions`).
    - **Example**: `python manage.py shell_plus`
    - **Documentation**: Opens a Python shell with models and other project components automatically imported.

27. **graph_models --output=<filename>**
    - **Description**: Generates a visual diagram of your models.
    - **Example**: `python manage.py graph_models --output=model_diagram.png`
    - **Documentation**: Useful for visualizing model relationships (requires `django-extensions` and `pygraphviz`).

28. **debugsqlshell**
    - **Description**: Opens a shell with SQL query logging enabled.
    - **Example**: `python manage.py debugsqlshell`
    - **Documentation**: Useful for debugging SQL queries (requires `django-debug-toolbar`).


### PostgreSQL Commands for Django Setup

1. **Login to PostgreSQL**
    - **Command**: `sudo -u postgres psql`
    - **Description**: Logs in as the PostgreSQL superuser.
    - **Example**: `sudo -u postgres psql`

2. **Create Database User**
    - **Command**: `CREATE USER <username> WITH PASSWORD '<password>';`
    - **Description**: Creates a new PostgreSQL user with a specified password.
    - **Example**: `CREATE USER myuser WITH PASSWORD 'mypassword';`

3. **Create Database**
    - **Command**: `CREATE DATABASE <dbname> OWNER <username>;`
    - **Description**: Creates a new PostgreSQL database and assigns ownership to the user.
    - **Example**: `CREATE DATABASE mydb OWNER myuser;`

4. **Grant Permissions to User**
    - **Command**: `GRANT ALL PRIVILEGES ON DATABASE <dbname> TO <username>;`
    - **Description**: Grants all privileges on the specified database to the user.
    - **Example**: `GRANT ALL PRIVILEGES ON DATABASE mydb TO myuser;`

5. **Exit PostgreSQL**
    - **Command**: `\q`
    - **Description**: Exits the PostgreSQL session.
    - **Example**: `\q`

