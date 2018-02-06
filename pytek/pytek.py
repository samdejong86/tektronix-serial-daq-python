"""

.. moduleauthor:: Brian Mearns <bmearns@ieee.org>

This is the top level module of the |PYTEK| package. It provides classes
for interfacing with various |tek| |oscopes| over a serial interface.

Most classes in this module are based on a specific series of devices, based on the
serial interface supported by the devices. There is currently only one class provided,
`TDS3k` which supports the TDS 3000 series of devices.


.. note:: **Serial Port not Included**

    :mod:`pytek` relies on a thirdparty serial port for communications, specifically
    one that matches the `pyserial`_ API. It is recommended that you simply use
    `pyserial` itself.

"""


import time
import re
from pytek.util import Configurator, Configurable


class TDS3k(Configurable):
    """
    The `TDS3k` class provides functions for interacting with the TDS 3000 series
    of |DPOs| from |tek|. Documentation on this interface is available from |tek|
    at `this link <tds3k_prog_man_>`_.
    """


    ID_REGEX = re.compile(r'^TEKTRONIX,TDS 3\d{3},')
    """
    The regular expression used to match the start of the `identify` string, 
    for `sanity_check`.

    .. code:: python

        r'^TEKTRONIX,TDS 3\d{3},'
        
    """

    def __init__(self, port):
        """
        Instances of this class are instantiated by passing in a serial port object, which
        supports the `pyserial`_ interface. This is the port that the object will use for
        interacting with the device. Configuration of this port depends on your device and
        your serial port implementation. Typical settings for RS232 are 9600 baud.

        Example::

            #Import class
            from pytek import TDS3k

            #Import pyserial
            import serial

            port = serial.Serial("COM1", 9600, timeout=1)
            tds = TDS3k(port)
            
            # ... do stuff with the tds object.

            #Closes the object's port.
            tds.close()

        .. warning:: Serial Port Timeout

            It is **very important** that you specify a timeout on your serial port.
            The `get_response` method (used by things like `screenshot` and `get_curve`)
            continue to read data until a read timesout, so if there is no timeout, it
            will never return.

        """
        self.port = port

    def close(self):
        """
        Closes the object's `port` by invoking it's `~serial.Serial.close` method.
        
        The object itself is not affected by this so if you
        call any methods that try to communicate over the port, it will be trying to 
        communicate over a closed port.
        """
        self.port.close()


    ### Basic Communications and Helpers ###

    def send_command(self, command, *args):
        """
        send_command(command, [arg1, [arg2, [...]]])

        Sends a command and any number of arguments to the device. Does not wait for response.
        
        .. seealso::

            * `send_query` - To send a query and get a one-line response.
        """
        args = [command] + list(args)
        temp = "%s\r" % " ".join(args)
        self.port.write(temp.encode('utf-8'))

    def send_query(self, query):
        """
        Sends a query to the device and reads back one line, returning that
        line (stripped of trailing whitespace).

        A '?' and a linebreak are automatically appended to the end of what
        you send.

        E.g.:

        >>> tek.send_query("*IDN")
        'TEKTRONIX,TDS 3034,0,CF:91.1CT FV:v2.11 TDS3GM:v1.00 TDS3FFT:v1.00 TDS3TRG:v1.00'
        >>>

        .. warning::

            This method turns off header echoing from the device. I.e., it sends `"HEADER OFF"`
            before anything else (through the `headers_off` method). If you're expecting headers
            to be on subsequently, you will need to turn them on with `"HEADER ON"`, or with the
            `headers_on` method.

        """
        self.headers_off()
        self.send_command("%s?" % query)
        returned = self.port.readline().rstrip()
        return returned.decode()

       
    def query_quoted_string(self, query):
        """
        Like `send_query`, but expects a quoted string as a response, and strips
        the quotes off the response before returning. Raises a `ValueError` if the
        response is not quoted.
        """
        resp = self.send_query(query)
        if resp[0] == '"' and resp[-1] == '"':
            return resp[1:-1]
        raise ValueError("Expected a quoted string, received: %r" % resp)

    def get_response(self):
        """
        Simply reads data from the object's `port`, one byte at a time until the port
        timesout on read. Returns the data as a `str`.

        Waits indefinitely for the first byte.
        """
        while True:
            data = self.port.read(1)
            if len(data):
                break
        while True:
            c = self.port.read(1)
            if len(c) == 0:
                break
            data += c
        return data



    ### Common Utility Commands ###

    def headers_off(self):
        """
        Sends the `"HEADER OFF"` command to the device, to disable echoing of headers (command names)
        in query responses from the device. Most methods that query the device will cause this
        to be sent. You can turn it back on with `headers_on`, or by sending the `"HEADER ON"` command.
        """
        self.send_command("HEADER", "OFF")

    def headers_on(self):
        """
        Sends the `"HEADER ON"` command to the device. See `headers_off` for details.
        """
        self.send_command("HEADER", "ON")

    def identify(self):
        """
        Convenience function for sending the `"*IDN"` query, with `send_query`, and returning the
        response from the device. This provides information about the device including model number,
        options, application modules, and firmware version.

        .. seealso::
            
            *   `sanity_check` uses the response from this method to determine if the connected
                device appears to a supported model.

        """
        return self.send_query("*IDN")

    def sanity_check(self):
        """
        Does a sanity check on the device to make sure that the way it identifies
        itself matches the expected response. Returns `True` if the sanity check passes,
        otherwise `False`.

        The device does not actually enforce this test, and will not perform it
        automatically (i.e., only if you call this method). This is for your sake
        so you don't waste time on a device that isn't compatible.
        
        .. seealso::
        
            * `identify`
            * `force_sanity`

        """
        id = self.identify()
        return TDS3k.ID_REGEX.match(id) is not None

    def force_sanity(self):
        """
        Does the `sanity_check` on the device, and raises an `Exception` if the check fails.
        """
        if not self.sanity_check():
            raise Exception("Unexpected string returned by identify.")



    ### ACQUISITION ###

    @Configurator.boolean("ACQUIRE:STATE", nocase=True)
    def acquire_state(flag):
        """
        +++
        The ``ACQUIRE:STATE`` setting is related to the "RUN / STOP" button on the device,
        and it basically configures whether the device is actually acquiring data or not.
        """
        if flag:
            return ('1', 'ON', 'RUN')
        return ('0', 'OFF', 'STOP')

    @Configurator.boolean("ACQUIRE:STOPAFTER", nocase=True)
    def acquire_single(flag):
        """
        +++
        The ``ACQUIRE:STOPAFTER`` setting is related to the "single sequence" button on the device.
        If `True`, then when the device is set to acquire (e.g., by passing `True`
        to `acquire_state`), it will only acquire a single sequence, and then
        stop automatically. Otherwise, it will continue to acquire until it is stopped.
        """
        if flag:
            return ('SEQ', 'SEQUENCE')
        return ('RUN', 'RUNST', 'RUNSTOP')


    ### TRIGGER ###

    def trigger(self):
        """
        Force the device to trigger, assuming it is in READY state (see `trigger_state`).

        This sends the ``TRIGGER FORCE`` command to the device.
        """
        self.send_command("TRIGGER", "FORCE");

    @Configurator.boolean("TRIGGER:A:MODE", nocase=True)
    def trigger_auto(flag):
        """
        The ``TRIGGER:A:MODE`` is related to the "AUTO" and "NORMAL" selections in
        the Trigger menu. If set to `True`, the trigger is in "AUTO (Untriggered roll)"
        mode, in which the device automatically generates a trigger if none is detected.

        Otherwise, the device is in "NORMAL" mode, in which the device waits for a valid trigger.
        """
        if flag:
            return ["auto",]
        return ["norm", "normal"]


    __TRIGGER_STATE_LIST = [
        ["auto", ],
        ["armed", ],
        ["ready", ],
        ["save", "sav"],
        ["trigger", "trig"],
    ]
    __TRIGGER_STATES = {}
    for seq in __TRIGGER_STATE_LIST:
        val = seq[0]
        for k in seq:
            __TRIGGER_STATES[k] = val

    def trigger_state(self):
        """
        Returns a string indicating the current trigger state of the device.
        This queries the ``TRIGGER:STATE`` setting on the device.

        The following list gives the possible return values:

        * **auto** - indicates that the oscilloscope is in auto mode and acquires data even in the absence of a trigger (see `trigger_auto`).
        * **armed** - indicates that the oscilloscope is acquiring pretrigger information. All triggers are ignored in this state.
        * **ready** - indicates that all pretrigger information has been acquired and the oscilloscope is waiting for a trigger.
        * **save** - indicates that acquisition is stopped or that all channels are off.
        * **trigger** - indicates that the oscilloscope has seen a trigger and is acquiring the posttrigger information.

        """
        val = self.send_query("TRIGGER:STATE")
        try:
            return self.__TRIGGER_STATES[val.lower()]
        except KeyError:
            return val




    ### Waveform and Data ###

    __WFM_PREAMBLE_FIELDS = (
            ('bytes_per_sample', int,),
            ('bits_per_sample', int,),
            ('encoding', str,),
            ('binary_format', str,),
            ('byte_order', str,),
            ('number_of_points', int,),
            ('waveform_id', str,),
            ('point_format', str,),
            ('x_incr', float,),
            ('pt_offset', int,),
            ('xzero', float,),
            ('x_units', str,),
            ('y_scale', float,),
            ('y_zero', float,),
            ('y_offset', float,),
            ('y_unit', str,),
    )
    __WFM_PREAMBLE_FIELD_NAMES = tuple(f[0] for f in __WFM_PREAMBLE_FIELDS)
    __WFM_PREAMBLE_FIELD_CONVERTERS = tuple(f[1] for f in __WFM_PREAMBLE_FIELDS)

    def get_waveform_preamble(self):
        """
        Queries the waveform preamble from the device, which details how a waveform or curve will be transferred
        from the device based on the current settings (as with `get_curve` or `get_waveform`, though note that
        both of those functions alter settings based on provided parameters, before retrieving the data).
        
        Returns a dictionary of preamble values.

        Example:

        >>> wfm_preamble = tds.get_waveform_preamble()
        >>> for k, v in wfm_preamble.iteritems():
        ...     print k, ":", repr(v)
        ...
        byte_order : 'MSB'
        binary_format : 'RP'
        x_incr : 1e-06
        y_scale : 0.08
        number_of_points : 10000
        y_unit : '"V"'
        encoding : 'BIN'
        y_zero : 0.0
        point_format : 'Y'
        waveform_id : '"Ch1, DC coupling, 2.0E0 V/div, 1.0E-3 s/div, 10000 points, Sample mode"'
        x_units : '"s"'
        y_offset : 128.0
        bits_per_sample : 8
        bytes_per_sample : 1
        pt_offset : 0
        xzero : -0.0045
        >>>

        """
        type(self.send_query("WFMPRE").split(';'))
        wfm = self.send_query("WFMPRE").split(';')
        return dict(zip(
            self.__WFM_PREAMBLE_FIELD_NAMES,
            [self.__WFM_PREAMBLE_FIELD_CONVERTERS[i](wfm[i]) for i in range(len(wfm))]
        ))

    point_count=0
    def get_curve(self, source="CH1", double=True, start=1, stop=10000, preamble=False, timing=False):
        """
        Queries a curve (waveform) from the device and returns it as a set of data points. Note that the
        points are simply unsigned integers over a fixed range (depending on the `double` parameter), they
        are not voltage values or similar. Use `get_waveform` to get scaled values in the proper units.

        .. warning::

            Note that this method will set waveform preamble and data parameters on the device, which have
            a persistent effect which could alter the behavior of future commands.

        If `preamble` or `timing` are `True`, returns a tuple: `(preamble_data, data, timing_data)`, where the
        `preamble_data` and `timing_data` are only present if the corresponding flag is set.

        If neither `preamble` nor `timing` is `True`, then just returns `data` as the sole argument (i.e., 
        `data`, not `(data,)`).

        In either case, `data` will be a sequence of data points for the curve. If the `double` parameter is
        `True` (the default), data points are each double-byte wide, in the range from 0 through 65535 (inclusive).
        This gives you maximum resolution on your data, but takes longer to transfer. Also note that the device
        does not necessarily have 16 bits of precision in measurement, but data will be left-aligned to the most
        significant bits.

        If `double` is `False`, then the data points are single-byte each, in the range from 0 through 255 (inclusive).
        
        Regardless of `double`, the minimum value corresponds to one vertical division *below* the bottom of
        the screen, and the maximum value corresponds to one vertical division *above* the top of the screen.

        :param str source:      Optional, specify the channel to copy the waveform from. Default is `"CH1"`.

        :param bool double:     Optional, if `True` (the default), data points are transferred 16-bits per
                                point, otherwise they are transferred 8-bits per point, which may cut off
                                least significant bits but will transfer faster.

        :param int start:       Optional, the data point to start at. The waveforms contains up to 10,000
                                data points, the first point is 1. The default value is 1. If you set this
                                param to `None`, it has the same effect as a 1.

        :param int stop:        Optional, the data point to stop at. See `start` for details. The default
                                value is 10,000 to transfer the entire waveform. If you set this to `None`,
                                it has the same effect as 10,000.

        :param bool preamable:  Controls whether or not the curve's preamble is included in the return value.
                                The curve's preamble is not the same as the waveform preamble that configures
                                the data. The curve's preamble is a string that is transmitted prior to the
                                curve's data points. I'm honestly not sure what it is, but it contains a
                                number which seems to increase with the number of data points
                                transferred.

        :param bool timing:     Controls whether or not timing information is included in the return value.
                                Timing gives the number of seconds it took to transfer the data, as a floating
                                point value.

        """
        width = 1
        if double:
            width = 2

        if start is None:
            start = 1
        if stop is None:
            stop = 10000

        #Configure the waveform the way we want it for transfer.
        self.headers_off()
        self.send_command("DATA:SOURCE", source)
        self.send_command("DATA:WIDTH", str(width))
        self.send_command("DATA:ENCDG", "RPBinary")
        self.send_command("WFMPRE:PT_Fmt", "Y")
        #self.send_command("DATA:START", str(start))
        #self.send_command("DATA:STOP", str(stop))

        #Check how many points it's going to send.        
        global point_count

        try:
            point_count
        except NameError:
            point_count = self.get_num_points()
                
        
        start_time = time.time()
        self.send_command("CURVE?")
        data = self.get_response()
        
        stop_time = time.time()
        
        #Strip trailing linebreak.
        
        if(data[-1] == 0x0A):
            data = data[:-1]

        length = len(data)
        preamble_len = length - width*point_count
        preamble_data = data[:preamble_len]

        points = []
        if width == 2:
            for i in range(preamble_len, len(data), 2):
                msB = data[i]
                lsB = data[i+1]
                points.append(msB << 8 | lsB)
                
        else:
            points = [ord(b) for b in data[preamble_len:]]

        #assert(len(points) == point_count)

        if preamble or timing:
            if preamble:
                ret = [preamble_data, points]
            else:
                ret = [points]
            if timing:
                ret.append(stop_time - start_time)
            return ret

        return points

    def get_waveform(self, source="CH1", double=True, start=1, stop=10000, preamble=False, timing=False):
        """
        Similar to `get_curve`, but uses `waveform premable <get_waveform_preamble>` data to properly scale
        the received data.

        If `preamble` or `timing` are `True`, returns a tuple: `(preamble_data, data, timing_data)`, where the
        `preamble_data` and `timing_data` are only present if the corresponding flag is set.

        If neither `preamble` nor `timing` is `True`, then just returns `data` as the sole argument (i.e., 
        `data`, not `(data,)`).

        `data` is a sequence of two tuples, giving the X and Y value for each point, in order across the X-acis
        from left to right. These are properly scaled based on the waveform settings, Giving, for instance,
        a value in Volts versus Seconds. Check `x_units` and `y_units` to get the actual units.
        """
        curve = self.get_curve(source=source, double=double, start=start, stop=stop, preamble=True, timing=True)
        wfm = self.get_waveform_preamble()
        xzero = float(wfm["xzero"])
        dx = float(wfm["x_incr"])
        ym = float(wfm["y_scale"])
        yoff = float(wfm["y_offset"])
        yzero = float(wfm["y_zero"])

        points = curve[1]
        #print("hello")
        #print(points)
        data = (
            (xzero + i*dx, ((points[i] - yoff) * ym) + yzero)
                for i in range(len(points))
        )
        if preamble or timing:
            if preamble:
                ret = [curve[0], data]
            else:
                ret = [data]
            if timing:
                ret.append(curve[2])
            return ret
        return data


    def get_num_points(self):
        """
        Queries the number of points that will be sent in a waveform or curve query,
        based on the current settings.

        This is relevant to functions like `get_waveform` and `get_curve`, but note
        that those functions set the `DATA:START` and `DATA:STOP` configuration options
        on the device based on provided parameters, thereby effecting the number of
        points.
        """
        a=self.send_query("WFMPRE:NR_PT")
        if a != '':
            point_count=a
            return int(a)
        else:
            return int(point_count)
        
    def y_units(self):
        """
        Returns a string giving the units of the Y axis based on the current waveform settings.

        Example:
        
        >>> tds.y_units()
        'V'
        >>>

        """
        return self.query_quoted_string("WFMPRE:YUNIT")

    def x_units(self):
        """
        Returns a string giving the units of the X axis based on the current waveform settings.
        Possible values include `'s'` for seconds and `'Hz'` for Hertz.

        Example:

        >>> tds.x_units()
        's'
        >>>

        """
        return self.query_quoted_string("WFMPRE:XUNIT")



    ### HARDCOPY ###

    def screenshot(self, ofile=None, fmt="RLE", inksaver=True, landscape=False):
        """
        Grabs a hardcopy/screenshot from the device.

        If `ofile` is `None` (the default), simply returns the data as a string. Otherwise, it
        writes the data to the given output stream.

        :param str fmt:     Optional, specify the format for the image. Valid values will vary
                            by device, but will be a subset of those listed below.
                            The default is "RLE" which gives a Windows Bitmap file.
                            
        :param bool inksaver:   Optional, if `True` (the default), puts the device into hardcopy-inksaver
                                mode, in which the background of the graticular is white, instead of black.
                                If `False`, sets the device to not be in inksaver mode.

        :param bool landscape:  Optional, if `False` (the default), the image will be in portrait mode,
                                which is probably what you want. If `True`, it will be in landscape mode,
                                which generally means the image will be rotated 90 degrees.

        **Possible supported formats**:

        The following is a list of the formats that may be supported, but individual devices will only
        support a subset of these. To see if your device supports a format, use `check_img_format`.

        *   **TDS3PRT** - For the TDS3000B series only, sets format for the TDS3PRT plug-in
            thermal printer.
        *   **BMP** - Grayscale bitmap. This is uncompressed, and very large and slow to transfer.
        *   **BMPColor** - Colored bitmap. Uncompressed, very large and slow to transfer.
        *   **DESKJET** - For the TDS3000B and TDS3000C series only, formatted for HP monochrome
            inkjet printers.
        *   **DESKJETC** - For the TDS3000B and TDS3000C series only, formatted for HP *color*
            inkjet printers.
        *   **EPSColor** - Colored Encapsulated PostScript.
        *   **EPSMono** - Monochrome Encapsulated PostScript.
        *   **EPSON** - For the TDS3000B and TDS3000C series only, supports Epson 9-pin
            and 24-pin dot matrix printers.
        *   **INTERLEAF** - Interleaf image object format.
        *   **LASERJET** - For the TDS3000B and TDS3000C series only, supports HP monochrome
            laser printers.
        *   **PCX** - PC Paintbrush monochrome image format.
        *   **PCXcolor** - PC Paintbrush color image format.
        *   **RLE** - Colored Windows bitmap (uses run length encoding for smaller file and faster transfer).
        *   **THINKJET** - For the TDS3000B and TDS3000C series only, supports HP monochrome inkjet printers.
        *   **TIFF** - Tag Image File Format.
        *   **DPU3445** - Seiko DPU-3445 thermal printer format.
        *   **BJC80** - For the TDS3000B and TDS3000C series only, supports Canon
            BJC-50 and BJC-80 color printers.
        *   **PNG** - Portable Network Graphics.


        .. note ::

            The fatest transfer seems to be **RLE**, with **TIFF** close behind (transfer times are less than
            one minute at 9600 baud). **BMP** and **BMPColor** take a very long time (more than five minutes
            at 9600 baud).
                                

        """
        self.send_command("HARDCOPY:FORMAT", str(fmt))
        self.send_command("HARDCOPY:LAYOUT", "landscape" if landscape else "portrait")
        self.send_command("HARDCOPY:INKSAVER", "on" if inksaver else "off")
        self.send_command("HARDCOPY:PORT", "RS232")
        self.send_command("HARDCOPY", "START")
        data = self.get_response()
        if ofile is not None:
            ofile.write(data)
            return None
        else:
            return data

    def check_img_format(self, fmt):
        """
        Tests if a hardcopy image format is supported by the device. This simply sets the `HARDCOPY:FORMAT`
        configuration value to the given format, and checks to see if it comes back as the same format.

        Return `True` if the format is supported, `False` otherwise.

        Resets the `HARDCOPY:FORMAT` back to where it was before returning.

        .. seealso::
            `screenshot`
        """
        orig_fmt = self.send_query("HARDCOPY:FORMAT")
        self.send_command("HARDCOPY:FORMAT", fmt)
        supported = (fmt.lower().startswith(self.send_query("HARDCOPY:FORMAT").lower()))
        self.send_command("HARDCOPY:FORMAT", orig_fmt)
        return supported




TDS3xxx = TDS3k
"""
 .. class: TDS3xxx(port)

    An alias for `TDS3k`.

"""

