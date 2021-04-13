from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client, get_tracker_conf
from django.conf import settings

class FdfsStorage(Storage):
    '''fdfs文件存储类，默认必须有_open，_save，exists方法'''
    # 注意：_open，_save，exists方法参数是固定的，不能添加或者减少
    # 在方法里面直接把文件写死路径，不利于文件的拓展，因此在settings文件里面设置好路径，以方便更好的拓展
    def __init__(self, client_conf=None, base_url=None):
        '''由于固定方法的参数，因此在init方法里面进行配置'''
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

        if base_url is None:
            base_url = settings.FDFS_BASE_URL
        self.base_url = base_url

    def _open(self,name, mode='rb'):
        '''打开文件时使用'''
        pass

    def _save(self, name, content):
        '''保存文件时使用'''
        # name为选择上传文件的名字
        # content为一个包含上传文件内容的File类的对象
        # 1、创建一个Fdfs_client对象，创建过程中需要指定一个client的配置文件，django在查找内容的时候，是从根目录开始查找，而不是相对路径，因此如果写相对路径就会报错
        # 由配置文件中的信息 得到 字典trackers
        tracker = get_tracker_conf(self.client_conf)
        client = Fdfs_client(tracker)
        # 上传文件到fdfs中，可以根据文件名上传，也可以根据文件内容上传，根据需求进行选择
        res = client.upload_by_buffer(content.read())
        # 以上返回的是一个字典，字典格式如下
        # dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': local_file_name,
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }
        # 只需要关注Status和Storage IP，Status为上传状态，成功的话返回Upload successed.字符串，Remote file_id为上传后返回的在fdfs中的文件名
        if res.get('Status') != 'Upload successed.':
            # 上传失败，为了代码的通用性，不能直接去捕获异常，可以抛出一个上传文件异常
            raise Exception('上传文件到fdfss失败')
        # 获取返回文件ID
        filename = res.get('Remote file_id').decode()
        return filename

    def exists(self, name):
        '''django判断文件名是否可用'''
        # 如果返回的内容为True，那么说明文件存在，False为文件不存在，由于没有使用django默认的上传系统，因此直接返回False即可
        return False

    def url(self, name):
        '''返回访问文件的url路径'''
        return self.base_url + name


