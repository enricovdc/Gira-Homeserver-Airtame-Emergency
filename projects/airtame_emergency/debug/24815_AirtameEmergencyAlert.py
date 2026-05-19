try:
    if(hsl20_4_debug_page==None or hsl20_4.Framework.get_framework_index()<7):
        raise NameError
except NameError:
    global hsl20_4_debug_page
    global traceback
    import traceback
    global sys
    import sys
    global thread
    import thread
    class hsl20_4_debug_page:
        class Section:
            def __init__(self, section_key):
                self.__context_id = section_key
                self.__fields = {}
                self.__exceptions = []
                self.__messages = []
                self.__callbacks = []
                self.__lock = thread.allocate_lock()
            def set_value(self, key, value):
                with self.__lock:
                    self.__fields[key] = value
            def add_value_to_average_field(self, key, value):
                with self.__lock:
                    if not self.__fields.has_key(key):
                        self.__fields[key] = float(value)
                    else:
                        self.__fields[key] = float((self.__fields[key] + value) / 2)
            def increase_counter_field(self, key):
                with self.__lock:
                    if not self.__fields.has_key(key):
                        self.__fields[key] = 1
                    else:
                        self.__fields[key] += 1
            def add_message(self, message):
                with self.__lock:
                    for item in self.__messages:
                        if item[1]==message:
                            item[0] = time.time()
                            item[2]+=1
                            return
                    self.__messages.append([time.time(),message,1])
                    self.__messages.sort()
                    if len(self.__messages)>25:
                        del self.__messages[0]
            def add_exception(self, comment=None):
                try:
                    text = None
                    try:
                        exc = sys.exc_info()
                        if (exc!=None) and (len(exc)>=3) and (exc[0]!=None):
                            lines = traceback.format_exception(exc[0], exc[1], exc[2])
                            text = ''
                            for line in lines[1:]:
                                text = text + line
                    finally:
                        del exc
                    if text!=None:
                        with self.__lock:
                            for item in self.__exceptions:
                                if item[1]==text and item[3]==comment:
                                    item[0] = time.time()
                                    item[2]+=1
                                    return
                            self.__exceptions.append([time.time(),text,1,comment])
                            self.__exceptions.sort()
                            if len(self.__exceptions)>15:
                                del self.__exceptions[0]
                except Exception as e:
                    print "add_exception()", e
            def get_debug_information(self):
                result = {}
                result["fields"] = {}
                result["messages"] = []
                result["exceptions"] = []
                with self.__lock:
                    for key in self.__fields:
                        result["fields"][key] = self.__fields[key]
                    for msg in self.__messages:
                        result["messages"].append([msg[0], msg[1], msg[2]])
                    for exc in self.__exceptions:
                        result["exceptions"].append([exc[0], exc[1], exc[2], exc[3]])
                return result
            def _internal_register(self, callback):
                idx = None
                try:
                    idx = self.__callbacks.index(callback)
                except:
                    pass
                if idx==None:
                    self.__callbacks.append(callback)
            def _internal_get_callbacks(self):
                return self.__callbacks
try:
    if(hsl20_4.Framework.get_framework_index()<7):
        raise NameError
except NameError:
    global hsl20_4
    import thread
    global Queue
    import Queue
    global os
    import os
    global asyncore
    import asyncore
    import time
    class hsl20_4:
        LOGGING_NONE = 0
        LOGGING_SYSLOG = 1
        _CONTEXT_THREAD_QUEUE_MAX_SIZE = 0
        _ASYNCORE_LOOP_TIMEOUT = 1
        _HSCTX = None
        class BaseModule:
            def __init__(self, homeserver_context, module_context):
                if hsl20_4._HSCTX==None:
                    hsl20_4._HSCTX = homeserver_context[0]
                self._mc = homeserver_context[0]
                self._context_id = module_context
                self._lock = thread.allocate_lock()
                self._module_id = None
                self._framework = None
                self._refenerce = None
                self._last_timer_ts=0
                self._refenerce=homeserver_context[3]
                self._input_values = {}
                for i in range(len(homeserver_context[2])): #EN
                    if(i>0):
                        self._input_values[i] = homeserver_context[2][i]
                self._remanent_values = {}
                for i in range(len(homeserver_context[1])): #SN
                    if i>2:
                        self._remanent_values[i-2] = homeserver_context[1][i]
                self._output_values = []
                if self._mc!=None:
                    self._framework = hsl20_4.Framework(self._mc, self._context_id, self)
                    self._module_id = self._framework._get_module_instance_id()
            def _get_module_id(self):
                return self._module_id
            def _get_module_class_id(self):
                return self._refenerce.LogikItem.ID
            def _hslfw_check_input_values(self, ec, en):
                idx = ec.index(True)
                self._input_values[idx]=en[idx]
                self._framework._run_in_context_thread(self.on_input_value, (idx, en[idx]))
            def _hslfw_check_output_values(self, sc, sn, ac, an):
                remanent_value_changed=False
                with self._lock:
                    self._last_timer_ts = time.time()
                    try:
                        for item in self._remanent_values:
                            idx = int(item)
                            if (sn[idx+2]!=self._remanent_values[item]):
                                remanent_value_changed=True
                                sc[idx+2] = 1
                                sn[idx+2] = self._remanent_values[item]
                        outputs_set=[]
                        while(len(self._output_values)>0):
                            item, value=self._output_values[0]
                            idx = int(item)
                            if idx in outputs_set:
                                break
                            else:
                                outputs_set.append(idx)
                            ac[idx] = 1
                            an[idx] = value
                            del self._output_values[0]
                        if (len(self._output_values) > 0):
                            self._mc.ZyklusWork.addQueue([0, self._refenerce])
                    except Exception as e:
                        pass
                return remanent_value_changed
            def _get_framework(self):
                return self._framework
            def _get_logger(self, logType, param):
                return self._framework._context.get_logger((logType,param))
            def _get_input_value(self, index):
                    if self._input_values.has_key(index):
                        return self._input_values[index]
                    else:
                        return None
            def on_input_value(self, index, value):
                pass
            def on_init(self):
                pass
            def _set_output_value(self, index, value):
                with self._lock:
                    if(len(self._output_values)>100):
                        raise RuntimeError("Outputqueue overflow (index=%s)" % index)
                    self._output_values.append((index, value))
                    if len(self._output_values) == 1 or (time.time() - self._last_timer_ts>2):
                        if self._refenerce!=None:
                            self._mc.ZyklusWork.addQueue([0, self._refenerce])
            def _can_set_output(self):
                return len(self._output_values)<100
            def _get_remanent(self, index):
                if self._remanent_values.has_key(index):
                    return self._remanent_values[index]
                else:
                    return None
            def _set_remanent(self, index, value):
                if isinstance(value, str):
                    self._remanent_values[index] = value[:30000]
                else:
                    self._remanent_values[index] = value
                if self._refenerce!=None:
                    self._mc.ZyklusWork.addQueue([0, self._refenerce])
        class Framework:
            _timer_thread=None
            def __init__(self, homeserver_context, module_context, module_instance):
                self._mc = homeserver_context
                self._context_id = module_context
                self._logger = None
                hsl20_4.Framework._init_globals(self._mc)
                self._context=hsl20_4._Context.get_context(homeserver_context, module_context)
                self._module_instance_id=self._context.register_module_instance(module_instance)
            @staticmethod
            def _init_globals(homeserver_context):
                if not hasattr(homeserver_context, "HSL20ID"):
                    homeserver_context.HSL20ID = 0
                if not hasattr(homeserver_context, "HSL20DBG"):
                    homeserver_context.HSL20DBG = {}
                try:
                    hsl20_4_timer
                    if not hasattr(homeserver_context, "HSL20TIMERTHREAD_3"):
                        homeserver_context.HSL20TIMERTHREAD_3 = {}
                        homeserver_context.HSL20TIMERTHREAD_3["instance"] = hsl20_4_timer._TimerThread()
                    hsl20_4.Framework._timer_thread=homeserver_context.HSL20TIMERTHREAD_3["instance"]
                except NameError:
                    pass
            @staticmethod
            def _get_global_debug_section():
                if not hsl20_4._HSCTX.HSL20DBG.has_key("global"):
                    hsl20_4._HSCTX.HSL20DBG["global"] = hsl20_4_debug_page.Section("GLOBAL")
                return hsl20_4._HSCTX.HSL20DBG["global"]
            @staticmethod
            def get_framework_index():
                return 7
            def _run_in_context_thread(self, method_to_call, args=None):
                self._context.run_in_context_thread(method_to_call, args)
            def _get_module_instance_id(self):
                return self._module_instance_id
            def _signal_asyncore_select_interrupt(self):
                self._context.signal_asyncore_select_interrupt()
            def get_homeserver_version(self):
                return self._mc.Debug.Version
            def get_homeserver_version_major(self):
                return int(self._mc.Debug.Version.split('.')[0])
            def get_homeserver_version_minor(self):
                return int(self._mc.Debug.Version.split('.')[1])
            def get_homeserver_serial_id(self):
                return self._mc.SystemID
            def get_homeserver_private_ip(self):
                return self._mc.Ethernet.IPAdr
            def get_project_id(self):
                return self._mc.ProjectID
            def get_coordinates(self):
                return (self._mc.UhrenList.gradBreite, self._mc.UhrenList.gradLaenge)
            def get_context(self):
                return self._context_id
            def get_instance_by_id(self, instance_id):
                return self._context.get_module_instance(instance_id)
            def get_instance_from_module_by_id(self, module_context, instance_id):
                context = hsl20_4._Context.get_context(self._mc, module_context)
                if context!=None:
                    return context.get_module_instance(instance_id)
                return None
            def create_http_server(self):
                return hsl20_4_http_server.Server(self, self._context.get_socket_map())
            def create_http_client(self):
                return hsl20_4_http_client.Client(self, self._context.get_socket_map())
            def create_tcp_client(self):
                return hsl20_4_tcp.Client(self, self._context.get_socket_map())
            def create_udp_unicast(self):
                return hsl20_4_udp.Unicast(self, self._context.get_socket_map())
            def create_udp_broadcast(self):
                return hsl20_4_udp.Broadcast(self, self._context.get_socket_map())
            def create_udp_multicast(self):
                return hsl20_4_udp.Multicast(self, self._context.get_socket_map())
            def create_timer(self):
                return hsl20_4_timer.Timer(self)
            def create_interval(self):
                return hsl20_4_timer.Interval(self)
            def create_debug_section(self):
                return self._context.get_debug_section()
            def create_md5_hash(self):
                return hsl20_4_crypto.MD5Hash()
            def create_sha1_hash(self):
                return hsl20_4_crypto.SHA1Hash()
            def create_sha224_hash(self):
                return hsl20_4_crypto.SHA2Hash(224)
            def create_sha256_hash(self):
                return hsl20_4_crypto.SHA2Hash(256)
            def create_sha384_hash(self):
                return hsl20_4_crypto.SHA2Hash(384)
            def create_sha512_hash(self):
                return hsl20_4_crypto.SHA2Hash(512)
            def create_aes(self):
                return hsl20_4_crypto.AESCipher()
            def resolve_dns(self, host):
                ip = self._mc.DNSResolver.getHostIP(host)
                if (len(ip)==0):
                    return None
                else:
                    return ip
        class _Context:
            @staticmethod
            def get_context(homeserver_context, context_id):
                if hasattr(homeserver_context, "HSL20DATA") and homeserver_context.HSL20DATA.has_key(context_id):
                    return homeserver_context.HSL20DATA[context_id]["instance"]
                else:
                    return hsl20_4._Context(homeserver_context, context_id)
            def __init__(self, homeserver_context, context_id):
                self._mc = homeserver_context
                self._context_id = context_id
                if not hasattr(homeserver_context, "HSL20DATA"):
                    homeserver_context.HSL20DATA = {}
                homeserver_context.HSL20DATA[context_id] = {}
                homeserver_context.HSL20DATA[context_id]["debug"] = None
                homeserver_context.HSL20DATA[context_id]["logger"] = None
                homeserver_context.HSL20DATA[context_id]["instances"] = {}
                homeserver_context.HSL20DATA[context_id]["context_queue"] = Queue.Queue(hsl20_4._CONTEXT_THREAD_QUEUE_MAX_SIZE)
                self.__thread_queue=homeserver_context.HSL20DATA[context_id]["context_queue"]
                homeserver_context.HSL20DATA[context_id]["instance"]=self
                self._global_debug_section=hsl20_4.Framework._get_global_debug_section()
                self.__start_context_queue_thread()
                self.__start_asyncore_loop()
            def register_module_instance(self, instance):
                self._mc.HSL20ID+=1
                instance_id=self._mc.HSL20ID
                self._mc.HSL20DATA[self._context_id]["instances"][instance_id] = instance
                return instance_id
            def get_module_instance(self, instance_id):
                if (self._mc.HSL20DATA[self._context_id]["instances"].has_key(instance_id)):
                    return self._mc.HSL20DATA[self._context_id]["instances"][instance_id]
                else:
                    return None
            def get_debug_section(self):
                if self._mc.HSL20DATA[self._context_id]["debug"]==None:
                    self._mc.HSL20DATA[self._context_id]["debug"] = hsl20_4_debug_page.Section(self._context_id)
                return self._mc.HSL20DATA[self._context_id]["debug"]
            def get_logger(self, create=None):
                if self._mc.HSL20DATA[self._context_id]["logger"] != None:
                    return self._mc.HSL20DATA[self._context_id]["logger"]
                try:
                    if create:
                        logType, param = create
                    else:
                        logType = hsl20_4.LOGGING_NONE
                    if logType==hsl20_4.LOGGING_NONE:
                        self._mc.HSL20DATA[self._context_id]["logger"] = hsl20_4.Logger()
                    elif logType==hsl20_4.LOGGING_SYSLOG:
                        self._mc.HSL20DATA[self._context_id]["logger"] = hsl20_4_logging_syslog(self, self._context_id, param)
                except NameError:
                    self._mc.HSL20DATA[self._context_id]["logger"] = hsl20_4.Logger()
                return self._mc.HSL20DATA[self._context_id]["logger"]
            def get_thread_count(self):
                cnt=0
                if self._mc.HSL20DATA[self._context_id].has_key("context_thread_id"):
                    cnt+=1
                if self._mc.HSL20DATA[self._context_id].has_key("asyncore_loop_thread_id"):
                    cnt+=1
                return cnt
            def get_socket_map(self):
                if not self._mc.HSL20DATA[self._context_id].has_key("socket_map"):
                    self._mc.HSL20DATA[self._context_id]["socket_map"] = {}
                return self._mc.HSL20DATA[self._context_id]["socket_map"]
            def run_in_context_thread(self, method_to_call, args=None):
                self.__thread_queue.put_nowait((method_to_call, args))
            def __start_context_queue_thread(self):
                if not self._mc.HSL20DATA[self._context_id].has_key("context_thread_id"):
                    self._mc.HSL20DATA[self._context_id]["context_thread_id"] = thread.start_new_thread(self.__thread_queue_consumer,())
            def __thread_queue_consumer(self):
                while(True):
                    method_to_call, args = self.__thread_queue.get(block=True)
                    try:
                        if(args==None):
                            method_to_call()
                        else:
                            method_to_call(*args)
                    except:
                        self._global_debug_section.add_exception()
                    self.__thread_queue.task_done()
            def __start_asyncore_loop(self):
                if(os.name!="nt"):
                    self._signal_pipe_out,self._signal_pipe_in=os.pipe()
                    import fcntl
                    fcntl.fcntl(self._signal_pipe_out,fcntl.F_SETFL,os.O_NONBLOCK)
                    self._signal_pipe_out=os.fdopen(self._signal_pipe_out,'r',0)
                    self._signal_pipe_in=os.fdopen(self._signal_pipe_in,'a',0)
                    dd=hsl20_4._dummyDispatcher()
                    dd._signal_pipe_out=self._signal_pipe_out
                    self.get_socket_map()[self._signal_pipe_out]=dd
                if not self._mc.HSL20DATA[self._context_id].has_key("asyncore_loop_thread_id"):
                    self._mc.HSL20DATA[self._context_id]["asyncore_loop_thread_id"] = thread.start_new_thread(self.__thread_asyncore_loop,())
            def signal_asyncore_select_interrupt(self):
                if(os.name!="nt"):
                    self._signal_pipe_in.write('1')
                    self._signal_pipe_in.flush()
            def __thread_asyncore_loop(self):
                socket_map=self.get_socket_map()
                while(True):
                    try:
                        asyncore.loop(map=socket_map, timeout=hsl20_4._ASYNCORE_LOOP_TIMEOUT)
                        time.sleep(0.1)
                    except:
                        try:
                            dd=socket_map[self._signal_pipe_out]
                            for fd, obj in socket_map.items():
                                try:
                                    obj.handle_error()
                                except:
                                    self._global_debug_section.add_exception()
                            socket_map.clear()
                            socket_map[self._signal_pipe_out]=dd
                        except:
                            self._global_debug_section.add_exception()
                        time.sleep(0)
            def __on_debug(self):
                result = {}
                try:
                    result["Socket Map Size"]=str(len(self.get_socket_map().keys()))
                    result["Thread Queue Size"]=str(self.__thread_queue.qsize())
                except:
                    self._global_debug_section.add_exception()
                return result
        class _dummyDispatcher:
            def readable(self):
                return True
            def writable(self):
                return False
            def handle_read_event(self):
                data=self._signal_pipe_out.read()
            def handle_error(self):
                pass
        class Logger:
            DISABLE = 100
            CRITICAL = 50
            ERROR = 40
            WARNING = 30
            INFO = 20
            DEBUG = 10
            NOTSET = 0
            def set_level(self, level):
                pass
            def info(self, msg):
                pass
            def error(self, msg):
                pass
            def debug(self, msg):
                pass
            def warning(self, msg):
                pass
            def critical(self, msg):
                pass
            def exception(self, comment):
                pass
import sys
__hsl20_sys_modules_keys=set(sys.modules.keys())
sys.path.insert(0,"/tmp/airtame_emergencyAirtameEmergencyAlert24815")
try:
    if(AirtameEmergencyAlert24815==None):
        raise NameError
except NameError:
    global AirtameEmergencyAlert24815
    try:
        import hsl20_4
    except ImportError:
        pass
    import base64
    import json
    import time
    import re
    try:
        from urllib2 import Request, urlopen, HTTPError, URLError
    except ImportError:
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError, URLError
    class AirtameEmergencyAlert24815(hsl20_4.BaseModule):
        def __init__(self, homeserver_context):
            hsl20_4.BaseModule.__init__(self, homeserver_context, "airtame_emergency")
            self.FRAMEWORK = self._get_framework()
            self.LOGGER = self._get_logger(hsl20_4.LOGGING_NONE,())
            self.PIN_I_TRIGGER=1
            self.PIN_I_CLEAR=2
            self.PIN_I_HEADLINE=3
            self.PIN_I_DESCRIPTION=4
            self.PIN_I_TEMPLATE=5
            self.PIN_I_IS_DRILL=6
            self.PIN_I_DURATION_SECONDS=7
            self.PIN_I_API_ENDPOINT=8
            self.PIN_I_API_KEY=9
            self.PIN_I_ALERT_ID_PREFIX=10
            self.PIN_I_TIMEOUT_SECONDS=11
            self.PIN_I_MAX_RETRIES=12
            self.PIN_I_DEBOUNCE_MS=13
            self.PIN_I_PAYLOAD_FORMAT=14
            self.PIN_I_SENDER_ID=15
            self.PIN_I_CAP_CATEGORY=16
            self.PIN_O_ACTIVE=1
            self.PIN_O_SUCCESS_PULSE=2
            self.PIN_O_ERROR_PULSE=3
            self.PIN_O_LAST_STATUS_CODE=4
            self.PIN_O_LAST_MESSAGE=5
            self.PIN_O_LAST_ALERT_ID=6
            self.REM_ACTIVE=1
            self.REM_ACTIVE_ALERT_ID=2
            self.REM_COUNTER=3
            self.REM_LAST_TRIG_VAL=4
            self.REM_LAST_TRIG_TS_MS=5
            self.REM_LAST_CLR_VAL=6
            self.REM_LAST_CLR_TS_MS=7
            self.REM_ACTIVE_SENT_TS=8
        ALLOWED_TEMPLATES = (
            "high", "medium", "low",
            "blank", "all-clear", "hold",
            "secure", "lockdown", "evacuate", "shelter",
        )
        CAP_REACHABLE_TEMPLATES = ("high", "medium", "low")
        ALLOWED_FORMATS = ("json", "cap")
        MAX_HEADLINE_LEN = 200
        MAX_DESCRIPTION_LEN = 2000
        CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
        TEMPLATE_TO_URGENCY = {
            "high": "Immediate", "lockdown": "Immediate", "evacuate": "Immediate",
            "shelter": "Immediate", "secure": "Immediate",
            "medium": "Expected", "hold": "Expected",
            "low": "Future", "all-clear": "Future", "blank": "Future",
        }
        SEVERITY_DEFAULT = "Severe"
        SEVERITY_DRILL = "Minor"
        def on_init(self):
            active = int(self._get_remanent(self.REM_ACTIVE) or 0)
            self._set_output_value(self.PIN_O_ACTIVE, 1 if active else 0)
            self._set_output_value(self.PIN_O_SUCCESS_PULSE, 0)
            self._set_output_value(self.PIN_O_ERROR_PULSE, 0)
            self._set_output_value(self.PIN_O_LAST_STATUS_CODE, 0)
            self._set_output_value(self.PIN_O_LAST_MESSAGE, "")
            self._set_output_value(
                self.PIN_O_LAST_ALERT_ID,
                self._get_remanent(self.REM_ACTIVE_ALERT_ID) or "",
            )
        def on_input_value(self, index, value):
            try:
                if index == self.PIN_I_TRIGGER:
                    if self._rising_edge(value, self.REM_LAST_TRIG_VAL,
                                         self.REM_LAST_TRIG_TS_MS):
                        self._handle_trigger()
                elif index == self.PIN_I_CLEAR:
                    if self._rising_edge(value, self.REM_LAST_CLR_VAL,
                                         self.REM_LAST_CLR_TS_MS):
                        self._handle_clear()
            except Exception as e:
                self._fail(0, "internal: " + str(e))
        def _pin_str(self, pin):
            v = self._get_input_value(pin)
            if v is None:
                return ""
            return v if isinstance(v, str) else str(v)
        def _pin_int(self, pin, default=0):
            v = self._get_input_value(pin)
            try:
                return int(v)
            except (TypeError, ValueError):
                return default
        def _config(self):
            headline = self._pin_str(self.PIN_I_HEADLINE) or "Emergency"
            description = (self._pin_str(self.PIN_I_DESCRIPTION)
                           or "Emergency alert from Gira HomeServer.")
            template = self._pin_str(self.PIN_I_TEMPLATE) or "high"
            is_drill = bool(self._pin_int(self.PIN_I_IS_DRILL, 0))
            duration = self._pin_int(self.PIN_I_DURATION_SECONDS, 300)
            endpoint = (self._pin_str(self.PIN_I_API_ENDPOINT)
                        or "https://airtame.cloud/api/v3.0/cloud/public/emergency-alerts")
            api_key = self._pin_str(self.PIN_I_API_KEY)
            prefix = self._pin_str(self.PIN_I_ALERT_ID_PREFIX) or "gira-hs"
            timeout = self._pin_int(self.PIN_I_TIMEOUT_SECONDS, 10)
            retries = self._pin_int(self.PIN_I_MAX_RETRIES, 2)
            debounce = self._pin_int(self.PIN_I_DEBOUNCE_MS, 1000)
            payload_format = (self._pin_str(self.PIN_I_PAYLOAD_FORMAT) or "json").lower()
            sender_id = self._pin_str(self.PIN_I_SENDER_ID) or "gira-homeserver"
            cap_category = self._pin_str(self.PIN_I_CAP_CATEGORY) or "Safety"
            return (headline, description, template, is_drill, duration,
                    endpoint, api_key, prefix, timeout, retries, debounce,
                    payload_format, sender_id, cap_category)
        def _rising_edge(self, value, prev_rem, ts_rem):
            cur = 1 if (value and int(value) != 0) else 0
            prev = int(self._get_remanent(prev_rem) or 0)
            self._set_remanent(prev_rem, cur)
            if cur and not prev:
                cfg = self._config()
                debounce_ms = cfg[10]
                now_ms = int(time.time() * 1000)
                last_ms = int(self._get_remanent(ts_rem) or 0)
                if last_ms == 0 or (now_ms - last_ms) >= debounce_ms:
                    self._set_remanent(ts_rem, now_ms or 1)
                    return True
            return False
        def _validate(self, alert_id, headline, description, template, duration,
                      payload_format="json"):
            if not alert_id:
                return "alert_id is required"
            if not headline:
                return "headline is required"
            if len(headline) > self.MAX_HEADLINE_LEN:
                return "headline exceeds %d characters" % self.MAX_HEADLINE_LEN
            if description and len(description) > self.MAX_DESCRIPTION_LEN:
                return "description exceeds %d characters" % self.MAX_DESCRIPTION_LEN
            if template not in self.ALLOWED_TEMPLATES:
                return ("template must be one of: high, medium, low, blank, "
                        "all-clear, hold, secure, lockdown, evacuate, shelter")
            if duration <= 0:
                return "duration_seconds must be > 0"
            if payload_format not in self.ALLOWED_FORMATS:
                return "payload_format must be one of: json, cap"
            return ""
        def _xml_escape(self, s):
            if s is None:
                return ""
            s = str(s)
            return (s.replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;")
                     .replace("\"", "&quot;")
                     .replace("'", "&apos;"))
        def _build_cap_alert(self, alert_id, sender_id, sent_iso, headline,
                             description, template, is_drill, duration_s,
                             category, expires_iso):
            urgency = self.TEMPLATE_TO_URGENCY.get(template, "Immediate")
            severity = self.SEVERITY_DRILL if is_drill else self.SEVERITY_DEFAULT
            status = "Actual"
            event_short = template.capitalize() if template else "Emergency"
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<alert xmlns="' + self.CAP_NS + '">'
                '<identifier>' + self._xml_escape(alert_id) + '</identifier>'
                '<sender>' + self._xml_escape(sender_id) + '</sender>'
                '<sent>' + sent_iso + '</sent>'
                '<status>' + status + '</status>'
                '<msgType>Alert</msgType>'
                '<scope>Public</scope>'
                '<info>'
                '<category>' + self._xml_escape(category) + '</category>'
                '<event>' + self._xml_escape(event_short) + '</event>'
                '<urgency>' + urgency + '</urgency>'
                '<severity>' + severity + '</severity>'
                '<certainty>Observed</certainty>'
                '<expires>' + expires_iso + '</expires>'
                '<senderName>' + self._xml_escape(sender_id) + '</senderName>'
                '<headline>' + self._xml_escape(headline) + '</headline>'
                '<description>' + self._xml_escape(description or "") + '</description>'
                '<instruction/>'
                '<area>'
                '<areaDesc></areaDesc>'
                '<circle></circle>'
                '</area>'
                '</info>'
                '</alert>'
            )
        def _build_cap_cancel(self, cancel_id, sender_id, cancel_sent_iso,
                              original_id, original_sent_iso, category, is_drill,
                              template="high"):
            urgency = self.TEMPLATE_TO_URGENCY.get(template, "Immediate")
            severity = self.SEVERITY_DRILL if is_drill else self.SEVERITY_DEFAULT
            status = "Actual"
            references = "%s,%s,%s" % (sender_id, original_id, original_sent_iso)
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<alert xmlns="' + self.CAP_NS + '">'
                '<identifier>' + self._xml_escape(cancel_id) + '</identifier>'
                '<sender>' + self._xml_escape(sender_id) + '</sender>'
                '<sent>' + cancel_sent_iso + '</sent>'
                '<status>' + status + '</status>'
                '<msgType>Cancel</msgType>'
                '<scope>Public</scope>'
                '<references>' + self._xml_escape(references) + '</references>'
                '<info>'
                '<category>' + self._xml_escape(category) + '</category>'
                '<event></event>'
                '<urgency>' + urgency + '</urgency>'
                '<severity>' + severity + '</severity>'
                '<certainty>Observed</certainty>'
                '<senderName>' + self._xml_escape(sender_id) + '</senderName>'
                '<headline></headline>'
                '<description></description>'
                '<instruction/>'
                '<area>'
                '<areaDesc></areaDesc>'
                '<circle></circle>'
                '</area>'
                '</info>'
                '</alert>'
            )
        def _iso8601_utc(self, epoch_s):
            return time.strftime("%Y-%m-%dT%H:%M:%S+00:00",
                                 time.gmtime(epoch_s))
        def _build_trigger_body(self, alert_id, headline, description, template,
                                is_drill, duration):
            payload = {
                "id": alert_id,
                "status": "Initiated",
                "template": template,
                "headline": headline,
                "description": description,
                "isDrill": bool(is_drill),
                "expiresAt": self._iso8601_utc(int(time.time()) + int(duration)),
            }
            return json.dumps(payload, separators=(",", ":"))
        def _build_clear_body(self, alert_id):
            return json.dumps({"id": alert_id, "status": "Resolved"},
                              separators=(",", ":"))
        def _mask(self, secret):
            if not secret:
                return ""
            n = len(secret)
            if n <= 4:
                return "*" * n
            return secret[:2] + "*" * (n - 4) + secret[-2:]
        def _basic_auth(self, api_key):
            raw = ("gira:" + api_key).encode("utf-8")
            return "Basic " + base64.b64encode(raw).decode("ascii")
        def _http_post(self, url, headers, body, timeout):
            req = Request(url=url, data=body.encode("utf-8"))
            req.get_method = lambda: "POST"
            for k, v in headers.items():
                req.add_header(k, v)
            try:
                resp = urlopen(req, timeout=timeout)
                return resp.getcode(), resp.read().decode("utf-8", "replace")
            except HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")
        def _send(self, body, endpoint, api_key, timeout_s, max_retries,
                  content_type="application/json"):
            if not endpoint.startswith("https://"):
                return 0, "", "config-endpoint"
            if not api_key:
                return 0, "", "config-key"
            headers = {
                "Authorization": self._basic_auth(api_key),
                "Content-Type": content_type,
                "Accept": "application/json",
            }
            body_json = body  # name retained for the rest of the method below
            attempt = 0
            backoff = 1.0
            while attempt <= max_retries:
                try:
                    status, resp_body = self._http_post(
                        endpoint, headers, body_json, timeout_s)
                except URLError as e:
                    attempt += 1
                    if attempt > max_retries:
                        return 0, "", "timeout"
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                if len(resp_body) > 500:
                    resp_body = resp_body[:500]
                if 200 <= status < 300:
                    return status, resp_body, ""
                if status in (401, 403):
                    return status, resp_body, "auth"
                if status == 429:
                    attempt += 1
                    if attempt > max_retries:
                        return status, resp_body, "rate-limit"
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                if 500 <= status < 600:
                    attempt += 1
                    if attempt > max_retries:
                        return status, resp_body, "server"
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return status, resp_body, "transport"
            return 0, "", "transport"
        def _next_alert_id(self, prefix):
            counter = int(self._get_remanent(self.REM_COUNTER) or 0) + 1
            self._set_remanent(self.REM_COUNTER, counter)
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            return "%s-%s-%d" % (prefix, stamp, counter)
        def _handle_trigger(self):
            cfg = self._config()
            (headline, description, template, is_drill, duration,
             endpoint, api_key, prefix, timeout, retries, _debounce,
             payload_format, sender_id, cap_category) = cfg
            alert_id = self._next_alert_id(prefix)
            msg = self._validate(alert_id, headline, description, template,
                                 duration, payload_format)
            if msg:
                self._fail(0, "validation: " + msg)
                return
            now_s = int(time.time())
            sent_iso = self._iso8601_utc(now_s)
            expires_iso = self._iso8601_utc(now_s + int(duration))
            if payload_format == "cap":
                body = self._build_cap_alert(alert_id, sender_id, sent_iso,
                                             headline, description, template,
                                             is_drill, duration, cap_category,
                                             expires_iso)
                content_type = "application/xml"
            else:
                body = self._build_trigger_body(alert_id, headline, description,
                                                template, is_drill, duration)
                content_type = "application/json"
            self.LOGGER.info(0, "[airtame] trigger (%s) id=%s key=%s"
                             % (payload_format, alert_id, self._mask(api_key)))
            status, resp, err = self._send(body, endpoint, api_key, timeout,
                                           retries, content_type=content_type)
            if err == "":
                self._set_remanent(self.REM_ACTIVE, 1)
                self._set_remanent(self.REM_ACTIVE_ALERT_ID, alert_id)
                self._set_remanent(self.REM_ACTIVE_SENT_TS, sent_iso)
                self._set_output_value(self.PIN_O_ACTIVE, 1)
                self._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
                self._set_output_value(self.PIN_O_LAST_ALERT_ID, alert_id)
                self._set_output_value(self.PIN_O_LAST_MESSAGE, "alert initiated")
                self._pulse(self.PIN_O_SUCCESS_PULSE)
            elif err in ("config-endpoint", "config-key"):
                self._fail(0, "config: " + err)
            else:
                self._fail(status, "HTTP %d (%s)" % (status, err))
        def _handle_clear(self):
            cfg = self._config()
            (_h, _d, template, is_drill, _du,
             endpoint, api_key, prefix, timeout, retries, _deb,
             payload_format, sender_id, cap_category) = cfg
            active = int(self._get_remanent(self.REM_ACTIVE) or 0)
            alert_id = self._get_remanent(self.REM_ACTIVE_ALERT_ID) or ""
            original_sent_iso = self._get_remanent(self.REM_ACTIVE_SENT_TS) or ""
            if not active or not alert_id:
                self.LOGGER.info(0, "[airtame] clear ignored (no active alert)")
                return
            if payload_format == "cap":
                cancel_id = self._next_alert_id(prefix + "-cancel")
                sent_iso = self._iso8601_utc(int(time.time()))
                body = self._build_cap_cancel(cancel_id, sender_id, sent_iso,
                                              alert_id, original_sent_iso,
                                              cap_category, is_drill, template)
                content_type = "application/xml"
            else:
                body = self._build_clear_body(alert_id)
                content_type = "application/json"
            self.LOGGER.info(0, "[airtame] clear (%s) id=%s"
                             % (payload_format, alert_id))
            status, resp, err = self._send(body, endpoint, api_key, timeout,
                                           retries, content_type=content_type)
            if err == "":
                self._set_remanent(self.REM_ACTIVE, 0)
                self._set_output_value(self.PIN_O_ACTIVE, 0)
                self._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
                self._set_output_value(self.PIN_O_LAST_MESSAGE, "alert resolved")
                self._pulse(self.PIN_O_SUCCESS_PULSE)
            elif err in ("config-endpoint", "config-key"):
                self._fail(0, "config: " + err)
            else:
                self._fail(status, "HTTP %d (%s)" % (status, err))
        def _pulse(self, pin):
            self._set_output_value(pin, 1)
            self._set_output_value(pin, 0)
        def _fail(self, status, message):
            self.LOGGER.error(0, "[airtame] " + message)
            self._set_output_value(self.PIN_O_LAST_STATUS_CODE, status)
            self._set_output_value(self.PIN_O_LAST_MESSAGE, message)
            self._pulse(self.PIN_O_ERROR_PULSE)

SN[1]=AirtameEmergencyAlert24815((MC, SN, EN, pItem))
SN[1].FRAMEWORK._run_in_context_thread(SN[1].on_init)
sys.path.remove("/tmp/airtame_emergencyAirtameEmergencyAlert24815")
for m in (set(sys.modules.keys())-__hsl20_sys_modules_keys):
    del sys.modules[m]
