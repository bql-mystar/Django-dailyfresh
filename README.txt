# 开启redis服务
redis-server /etc/redis/redis.conf

# 开启fdfs
service fdfs_trackerd start
service fdfs_storaged start

# 开启nginx服务
cd /usr/local/nginx/sbin/
./nginx

# 启动celery
# 切换到对应的django目录下
celery -A celery_tasks.tasks worker -l info




# 服务器IP发生变化，对应的配置修改
cd /etc/fdfs/
vim mod_fastdfs.conf
vim storage.conf
vim client.conf

# 将以上三个文件对应的tracker_server内容进行对应的修改
tracker_server=服务器对应的ip:22122

# 修改redis.conf下对应的ip
1、vim /etc/redis/redis.conf
2、将bind对应的ip修改为服务器ip


# 修改setting.py文件下对应的内容
1、修改数据库对应的ip
2、修改django缓存配置，即CACHES
3、修改fdfs存储服务器上nginx对应的ip