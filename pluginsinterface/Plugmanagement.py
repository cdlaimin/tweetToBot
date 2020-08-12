#加载所有插件
import glob
import importlib
import os
import traceback
import functools
from pluginsinterface.EventHandling import StandEven
from enum import Enum
from helper import getlogger
import config
logger = getlogger(__name__)
"""
插件兼容层
*插件管理大师(划掉)
支持发送事件
"""
#插件列表
PluginsManageList = {}
#优先级插件列表
pluglist = []
for _ in range(10):
    pluglist.append(list())
#启动回调列表
plugstartfuncs = []

PLUGADMIN = config.PLUGADMIN
DEBUG = config.DEBUG
"""
插件相关类
"""
class NoInstance(type):
    #通过__call___方法控制访问
    def __call__(self,*args,**kwargs):
        raise TypeError('禁止实例化')

#消息类型 private、group、tempprivate、tempgroup  私聊(一对一)、群聊(一对多)、临时聊天(一对一)、临时群聊(一对多)
class PlugMsgTypeEnum:
    """
        插件消息类型定义类
        不可实例化 多个类型过滤使用 | 分隔(例：PlugMsgTypeEnum.private | PlugMsgTypeEnum.group)
        unknown #未知类型(仅用于事件生成过程)
        private #私聊
        group #群聊
        tempprivate #临时私聊
        tempgroup #临时群聊
        plugadmin #插件管理者(仅用于消息过滤时识别管理者)
    """
    unknown = 0
    private = 1
    group = 2
    tempprivate = 4
    tempgroup = 8
    plugadmin = 16 #插件管理者
    allowall = 1 | 2 | 4 | 8 | 16
class PlugMsgReturn(Enum):
    """
        插件返回值定义类
        不可实例化
        Ignore 消息忽略
        Intercept 消息拦截
    """
    Ignore = 1 
    Intercept = 2 
class PluginsManage:
    """
        插件管理器
        实例化后将自动加入插件列表
        删除时自动从插件列表中移除

        :param modulename: 插件所属模块
        :param name: 插件名称
        :param version: 插件版本
        :param auther: 插件作者
        :param des: 插件描述
        :param level: 插件优先级(0-9),0为最高优先级
    """
    #module名，昵称，描述，优先级(0-9，决定插件何时处理消息)
    def __init__(self,modulename:str,name:str,version:str,auther:str,des:str,level:int = 4):
        global pluglist,PluginsManageList
        if level < 0 or level > 9:
            raise Exception('插件优先级设置异常！')
        self.open = True
        self.modulename = modulename
        self.name = name
        self.version = version
        self.auther = auther
        self.des = des
        self.funcs = []
        self.perfuncs = []
        self.level = level
        if self.modulename in PluginsManageList:
            raise Exception('函数重复注册！')
        pluglist[self.level].append(self)
        PluginsManageList[self.modulename] = self
    def __del__(self):
        global pluglist,PluginsManageList
        pluglist[self.level].remove(self)
        del PluginsManageList[self.modulename]
    def __hash__(self):
        return hash(self.modulename)
    def __eq__(self,other):
        return self.modulename == other.modulename
    def changelevel(self,level:int = 4):
        global pluglist
        if level < 0 or level > 9:
            raise Exception('插件优先级设置异常！')
        pluglist[self.level].remove(self)
        self.level = level
        pluglist[self.level].append(self)
    @staticmethod
    def baleFuncInfo(module,funcname,msgfilter,argfilter,des,limitMsgType,allow_anonymous,at_to_me):
        return (
            module,
            funcname,
            msgfilter,
            argfilter,
            des,
            limitMsgType,
            allow_anonymous,
            at_to_me
        )
    def addPerFunc(self,func,checkmodule = True) -> bool:
        if checkmodule and func.__module__ != self.modulename:
            return False
        self.perfuncs.append(func)
        return True
    def addFunc(self,func,funcinfo:tuple,checkmodule = True) -> bool:
        if checkmodule and func.__module__ != self.modulename:
            return False
        self.funcs.append((func,funcinfo))
        return True
    def _eventArrives(self,even:StandEven) -> PlugMsgReturn:
        #插件的事件处理，返回值决定消息是否放行，PlugMsgReturn.Intercept拦截、PlugMsgReturn.Ignore放行
        if not self.open:
            return PlugMsgReturn.Ignore
        even.sourcefiltermsg = even.message.toStandStr().strip()
        even.filtermsg = even.sourcefiltermsg
        for func in self.perfuncs:
            try:
                res = func(even)
                if res == PlugMsgReturn.Intercept:
                    return PlugMsgReturn.Ignore
            except:
                #处理插件异常(前置插件异常时将拦截所有消息的向下传递-即后续函数被忽略)
                s = traceback.format_exc(limit=10)
                logger.error(s)
                logger.error("插件函数执行异常！请检查插件->{name}-{version}-{auther}".format(
                        self.name,
                        self.version,
                        self.auther
                    ))
                return PlugMsgReturn.Ignore
        for fununit in self.funcs:
            try:
                even.filtermsg = even.sourcefiltermsg
                res = fununit[0](even)
                if res == PlugMsgReturn.Intercept:
                    return res
            except:
                #处理插件异常
                s = traceback.format_exc(limit=10)
                logger.error(s)
                logger.error("插件函数执行异常！请检查插件->{name}-{version}-{auther}".format(
                        self.name,
                        self.version,
                        self.auther
                    ))
        return PlugMsgReturn.Ignore
    def getPlugDes(self,simple = True) -> str:
        """
            获取插件描述
            :param simple: 为True时返回简化消息(默认True)
            :return: 字符串
        """
        msg = "插件名：{name}\n版本：{version}\n作者：{auther}\n描述：{des}".format(
                    name = self.name,
                    version = self.version,
                    auther = self.auther,
                    des = self.des,
                )
        if not simple:
            msg = '所属模块：{module}\n插件优先级：{level}'.format(module = self.modulename,level = self.level)
        return msg
    def __getFuncDes(self,funcinfo:tuple,simple = True):
        if simple:
            return funcinfo[4]
        return "{1}|{2}|{4}|{5}|{6}|{7}".format(*funcinfo)
    def getPlugFuncsDes(self,simple = True):
        """
            获取插件函数描述
            :param simple: 为True时返回简化消息(默认True)
            :return: 字符串
        """
        msg = '' if simple else '函数名|消息过滤器|描述|限制标识|允许匿名|AtBot'
        for fununit in self.funcs:
            msg += "\n" + self.__getFuncDes(fununit[1],simple=simple)
        return msg
    def switchPlug(self,switch:bool = None):
        """
            切换插件状态
            全局切换，末端控制请使用权限模块控制
            :param switch: False时插件关闭，为True时开启，为空时开则关关则开
            :return: 字符串
        """
        if not switch:
            switch = not self.open
        self.open = switch
"""
插件注册等静态函数
"""
from pluginsinterface.PlugFilter import PlugArgFilter,PlugMsgFilter
def plugGet(modulename:str) -> PluginsManage:
    """
        通过模块名称获取插件管理器

        :param name: 插件名
        :param level: 插件消息处理优先级，0-9级，0级最优先
        :param modulename: 手动指定注册的插件模块名，默认为被装饰函数所在模块，一般不需要指定
        :return: Func
    """
    global PluginsManageList
    if modulename in PluginsManageList:
        return PluginsManageList[modulename]
    return None
def plugLoads(plugpath = 'plugins'):
    """
        导入指定路径或者目录下的插件，并返回插件信息

        :param plugpath: 要导入的插件路径(相对路径)，可以导入指定目录下的py插件
        :return: None
    """
    global pluglist,plugstartfuncs
    #加载插件
    plugsearchpath = os.path.join(plugpath,'**.py')
    #modules_dict = {}
    module_paths = glob.glob(plugsearchpath)
    plugcount = 0
    for path in module_paths:
        module_name = path.replace(os.sep, '.')[:-3]
        try:
            importlib.import_module(module_name)
        except:
            #处理插件异常
            s = traceback.format_exc(limit=10)
            logger.error(s)
            logger.error("模块加载异常！请检查模块->{0}".format(module_name))
        else:
            plugcount += 1
            if DEBUG:
                logger.info("成功加载插件："+module_name)
    logger.info("插件加载完毕，共加载插件{0}".format(plugcount))
    for func in plugstartfuncs:
        try:
            func(plugGet(func.__module__))
        except:
            #处理插件异常
            s = traceback.format_exc(limit=10)
            logger.error(s)
            logger.error("插件启动回调异常！请检查模块->{0}".format(func.__module__))

def plugRegistered(name:str,modulename:str = '',level:int = 4):
    """
        插件注册函数(插件名，插件消息处理优先级0-9，默认4)
        每个插件必须运行一次，也只能运行一次，且运行在注册函数之前
        没有运行注册函数前的注册会被视为无效注册
        被装饰函数必须返回如下格式插件描述
        {
            'plugmanagement':'1.0',#插件注册管理(原样)
            'version':'x.x',#插件版本
            'auther':'xxx',#插件作者
            'des':'描述信息'#插件描述
        }
        
        :param name: 插件名
        :param level: 插件消息处理优先级，0-9级，0级最优先
        :param modulename: 手动指定注册的插件模块名，默认为被装饰函数所在模块，一般不需要指定
        :return: Func
        """
    global logger
    if level < 0 or level > 9:
        raise Exception('插件优先级设置异常！')
    if modulename and type(modulename) != str:
        raise Exception('模块名称异常')
    if modulename:
        logger.warning('手动加载插件:{modulename}'.format(modulename = modulename))
    
    def decorate(func):
        nonlocal modulename,level,name
        @functools.wraps(func)
        def wrapper():
            return func()
        
        #获取插件描述,并检查描述
        plugdes = func()
        if type(plugdes) != dict:
            raise Exception('插件注册不合法，注册返回值类型异常！')
        if 'plugmanagement' not in plugdes:
            raise Exception('插件注册不合法，注册返回值中的plugmanagement键值不存在！')
        if plugdes['plugmanagement'] not in ('1.0'):
            raise Exception('插件注册不合法，注册返回值中的plugmanagement键值不在可兼容版本列表！')
        if 'version' not in plugdes:
            raise Exception('插件注册不合法，注册返回值中的version键值不存在！')
        if 'auther' not in plugdes:
            raise Exception('插件注册不合法，注册返回值中的auther键值不存在！')
        if 'des' not in plugdes:
            raise Exception('插件注册不合法，注册返回值中的des键值不存在！')
        if type(plugdes['version']) != str:
            raise Exception('插件注册不合法，注册返回值中的version键值类型异常！')
        if type(plugdes['auther']) != str:
            raise Exception('插件注册不合法，注册返回值中的auther键值类型异常！')
        if type(plugdes['des']) != str:
            raise Exception('插件注册不合法，注册返回值中的des键值类型异常！')
        if not modulename:
            modulename = func.__module__
        #插件注册
        plug = PluginsManage(modulename,name,plugdes['version'],plugdes['auther'],plugdes['des'],level)
        logger.info('插件已注册{module}-{name}-{auther}-{version}'.format(
            module = plug.modulename,
            name = plug.name,
            auther = plug.auther,
            version = plug.version
            ))
        return wrapper
    return decorate
def on_plugloaded():
    """
        插件加载完毕回调
        被装饰函数
            仅一个参数，参数为当前模块绑定的插件，若无插件绑定，则为None
            参数 plug:PluginsManage
            返回值 无
    """
    def decorate(func):
        global plugstartfuncs
        @functools.wraps(func)
        def wrapper(plug:PluginsManage):
            return func(plug)
        plugstartfuncs.append(wrapper)
        return wrapper
    return decorate
def on_preprocessor(
    limitMsgType:PlugMsgTypeEnum = PlugMsgTypeEnum.allowall,
    allow_anonymous = True,at_to_me = False
    ):
    """
        前置消息过滤器(仅对模块所属插件生效·以模块名标识)
        被装饰函数
            函数根据返回的PlugMsgReturn值判断是否拦截消息，不返回数据时默认放行(放行用以允许插件函数处理)
            参数 even:StandEven
            返回值 PlugMsgReturn类型
        注：过滤器相关请查看对应过滤类
        :param limitMsgType: PlugMsgTypeEnum类 消息标识过滤器
        :param allow_anonymous: 是否允许匿名消息
        :param at_to_me: 需要艾特BOT
    """
    def decorate(func):
        nonlocal limitMsgType,allow_anonymous,at_to_me
        @functools.wraps(func)
        def wrapper(even:StandEven) -> PlugMsgReturn:
            if even.anonymous and not allow_anonymous or \
                not even.atbot and at_to_me or \
                not even.msgtype & limitMsgType:
                return PlugMsgReturn.Intercept
            res = func(even)
            if res == None:
                return PlugMsgReturn.Ignore
            return res
        if func.__module__ in PluginsManageList:
            if DEBUG:
                logger.info('前置函数注册{module}.{name}'.format(
                    module = wrapper.__module__,
                    name = wrapper.__name__
                    ))
            PluginsManageList[func.__module__].addPerFunc(
                wrapper,
                checkmodule=False
                )
        else:
            logger.warning('前置函数{module}.{name}所在模块未注册为插件，注册失败'.format(
                module = wrapper.__module__,
                name = wrapper.__name__
                ))
        return wrapper
    return decorate
def on_message(
        msgfilter:PlugMsgFilter = '',argfilter:PlugArgFilter = '',des:str = '',
        limitMsgType:PlugMsgTypeEnum = PlugMsgTypeEnum.allowall,
        allow_anonymous = False,at_to_me = True
        ):
    """
        注册消息函数(消息过滤器,参数过滤器,函数描述,消息类型限制,群聊限制-暂未实现,是否允许匿名,需要指定BOT)
        被装饰函数
            函数根据返回的PlugMsgReturn值判断是否拦截消息，不返回数据时，发送过回复则拦截，否则放行
            参数 even:StandEven
            返回值 PlugMsgReturn类型
        注：过滤器相关请查看对应过滤类
        :param msgfilter: PlugMsgFilter类 消息过滤器，可以为正则表达式字符串
        :param argfilter: PlugArgFilter类 参数过滤器，可以为文本 详见PlugArgFilter类注释
        :param des: 函数描述(例：“!翻译 待翻译内容 - 机器翻译”)，可使用 !help 插件昵称 查看描述预览
        :param limitMsgType: 消息标识过滤器
        :param allow_anonymous: 是否允许匿名消息
        :param at_to_me: 需要艾特BOT
    """
    global PluginsManageList,logger
    #logger.info('on_msg初始化')
    if type(msgfilter) == str:
        msgfilter = PlugMsgFilter(msgfilter)
    if not isinstance(msgfilter,PlugMsgFilter):
        raise Exception('消息过滤器参数不兼容！')
    if type(argfilter) == str:
        argfilter = PlugArgFilter(argfilter)
    if not isinstance(argfilter,PlugArgFilter):
        raise Exception('参数过滤器参数不兼容！')
    
    def decorate(func):
        nonlocal msgfilter,argfilter,des,limitMsgType,allow_anonymous,at_to_me
        @functools.wraps(func)
        def wrapper(even:StandEven) -> PlugMsgReturn:
            #消息过滤，
            if even.anonymous and not allow_anonymous or \
                not even.atbot and at_to_me or \
                not even.msgtype & limitMsgType:
                return PlugMsgReturn.Ignore
            filtermsg = even.filtermsg
            if not msgfilter.filter(filtermsg):
                return PlugMsgReturn.Ignore
            #参数处理
            even.argstr = msgfilter.replace(filtermsg)
            res = argfilter.filter(even.argstr)
            if not res[0]:
                nick = res[1]
                errdes = res[2]
                argdes = res[3]
                even.send("{nick}，{errdes}，参数说明 {des}".format(
                    nick = nick,
                    errdes = errdes,
                    des = argdes
                    ))
                return PlugMsgReturn.Intercept
            even.filterargs = res[1]
            res = func(even)
            if res == None:
                if even.hasReply:
                    return PlugMsgReturn.Intercept
            return res
        if func.__module__ in PluginsManageList:
            if DEBUG:
                logger.info('函数注册{module}.{name}·{des}'.format(
                    module = wrapper.__module__,
                    name = wrapper.__name__,
                    des = des
                    ))
            PluginsManageList[func.__module__].addFunc(
                wrapper,
                PluginsManage.baleFuncInfo(
                    wrapper.__module__,wrapper.__name__,
                    msgfilter,argfilter,des,limitMsgType,
                    allow_anonymous,at_to_me
                ),
                checkmodule=False
                )
        else:
            logger.warning('函数{module}.{name}·{des}所在模块未注册为插件，注册失败'.format(
                module = wrapper.__module__,
                name = wrapper.__name__,
                des = des
                ))
        return wrapper
    return decorate

"""
事件处理
"""
def __eventArrives(even:StandEven) -> PlugMsgReturn:
    global pluglist
    if DEBUG:
        logger.info(even.toStr())
    for i in range(len(pluglist)):
        for plug in pluglist[i]:
            res = plug._eventArrives(even)
            if res == PlugMsgReturn.Intercept:
                if DEBUG:
                    logger.info('插件{modulename}·{name}拦截了这条消息'.format(
                        modulename = plug.modulename,
                        name = plug.name
                        ))
                return PlugMsgReturn.Intercept
    if DEBUG:
        logger.info('没有插件处理此消息')
    return PlugMsgReturn.Ignore
def _send_even(even:StandEven) -> PlugMsgReturn:
    return __eventArrives(even)
