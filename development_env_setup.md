Install Editable source
-------------------------
 % pyenv virtualenv 3.6.5 p3nav
 % source source /Users/yiy/.pyenv/versions/3.6.5/envs/p3nav/bin/activate
 % pip install -e git+https://github.com/yytsui/nav.git#egg=nav
 
 
 Configuration
 --------------
  % nav config path
  
  copy sample config to nav
  % nav config install /Users/yiy/.local/etc/nav
   
  % nav config where
  
  
 Run web server
 ---------------
  % python setup.py build_sass  # sass -> css
  % add file ./python/nav/django/local_settings.py and set DEBUG=True
  % python python/nav/django/manage.py runserver 0.0.0.0:8004 
  
 Run Postgres and Graphite Dockers
 ----------------------------------
  % docker-compose up postgres  graphite
 

 Run Daemon Process and Setup cron jobs
 -------------------------------------
  % nav start
  % cd /tmp/ to check log files
  % crontab -e to check cron jobs
  % nav stop to stop daemon process and remove cron jobs
  

