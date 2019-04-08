

# TODO:
# Both microcode and ctree use the following class:
#   lvar_t       a local variable. may represent a stack or register
#                variable. a variable has a name, type, location, etc.
#                the list of variables is stored in mba->vars.
#   lvar_locator_t holds a variable location (vdloc_t) and its definition
#                address.
#   vdloc_t      describes a variable location, like a register number,
#                a stack offset, or, in complex cases, can be a mix of
#                register and stack locations. very similar to argloc_t,
#                which is used in ida. the differences between argloc_t
#                and vdloc_t are:
#                  - vdloc_t never uses ARGLOC_REG2
#                  - vdloc_t uses micro register numbers instead of
#                    processor register numbers
#                  - the stack offsets are never negative in vdloc_t, while
#                    in argloc_t there can be negative offsets

#class HxFlagCvar(object):
#    """
#        Enum of the value used in the :meth:`~HxVar.flags` of the hexrays
#        local variable :class:`HxVar` . Comment are from hexrays.
#    """
#    CVAR_USED    0x00000001 #: is used in the code?                      
#    CVAR_TYPE    0x00000002 #: the type is defined?                      
#    CVAR_NAME    0x00000004 #: has nice name?                            
#    CVAR_MREG    0x00000008 #: corresponding mregs were replaced?        
#    CVAR_NOWD    0x00000010 #: width is unknown                          
#    CVAR_UNAME   0x00000020 #: user-defined name                         
#    CVAR_UTYPE   0x00000040 #: user-defined type                         
#    CVAR_RESULT  0x00000080 #: function result variable                  
#    CVAR_ARG     0x00000100 #: function argument                         
#    CVAR_FAKE    0x00000200 #: fake return variable                      
#    CVAR_OVER    0x00000400 #: overlapping variable                      
#    CVAR_FLOAT   0x00000800 #: used in a fpu insn                        
#    CVAR_SPOILED 0x00001000 #: internal flag, do not use: spoiled var    
#    CVAR_MAPDST  0x00002000 #: other variables are mapped to this var    
#    CVAR_PARTIAL 0x00004000 #: variable type is partialy defined         
#    CVAR_THISARG 0x00008000 #: 'this' argument of c++ member functions   
#    CVAR_FORCED  0x00010000 #: variable was created by an explicit request otherwise we could reuse an existing var  

from bip.base import type as biptype
from ida_hexrays import lvar_saved_info_t, lvar_uservec_t, save_user_lvar_settings


class HxLvar(object):
    """
        Python object for representing a local variable of hexrays.

        .. todo:: flags (not accessible publicly)
        ., todo:: setters
        ., todo:: type info
        .. todo:: raccord with cfunc_t (HxFunc)

        .. todo:: test
    """

    def __init__(self, lvar, hxcfunc, persistent=True):
        """
            Constructor for the :class:`HxLvar` representing a local variable
            from hexrays.

            .. todo:: test

            :param lvar: A ``lvar_t`` object from hexrays (those are swig
                proxy) which is the ida variable corresponding to this object.
            :param hxcfunc: The :class:`HxCFunc` object to which this local
                variable is attached.
            :param bool persistent: Indicate if change to this object using
                the setter should be made persistent in the idb. True by
                default. See :meth:`~HxLvar.save` for more information.
        """
        self._lvar = lvar
        self._hxcfunc = hxcfunc
        self._persistent = persistent

    #################################### BASE ################################

    @property
    def name(self):
        """
            Property which return the name of this local variable.

            :return str: The name of the variable
        """
        return self._lvar.name

    @name.setter
    def name(self, value):
        """
            Setter for the name of this local variable.
            
            If this local variable is not set as persistent (True by default)
            this will not be saved in the idb. See :meth:`~HxLvar.save` for
            more information.

            :param str value: The new name of this local variable.
        """
        self._lvar.name = value
        self._lvar.set_user_name()
        if self._persistent:
            self.save()

    @property
    def size(self):
        return self._lvar.width

    @property
    def comment(self):
        """
            Property which return the comment of the lvar.

            .. todo:: test

            :return: The value of the comment or ``None`` if there is no
                comment.
            :rtype: :class:`str`
        """
        return self._lvar.cmt

    @comment.setter
    def comment(self, value):
        """
            Setter for the comment of this local variable.
            
            If this local variable is not set as persistent (True by default)
            this will not be saved in the idb. See :meth:`~HxLvar.save` for
            more information.

            :param str value: The new comment of this local variable.
        """
        self._lvar.cmt = value
        if self._persistent:
            self.save()

    @property
    def _ida_tinfo(self):
        """
            Internal property which allow to get the ``tinfo_t`` swig proxy
            from IDA associated with this lvar.

            :return: The ``ida_typeinf.tinfo_t`` object (swig proxy) provided
                by IDA for this variable.
        """
        return self._lvar.type()

    @property
    def type(self):
        """
            Property which return the object, which inherit from
            :class:`IdaType`, corresponding to the type of this local
            variable.
            
            Because of the handling of the type in IDA the object
            returned is a copy of the type of this local variable. For
            changing the type of this variable it is necessary to use the
            setter of this property. For more information about this problem
            see :class:`IdaType` .

            :return: An object which inherit from :class:`IdaType` and
                represent the type of this local variable.
        """
        return biptype.IdaType.GetIdaType(self._ida_tinfo)

    @type.setter
    def type(self, value):
        """
            Property setter which take an object inherited from
            :class:`IdaType` and set the type of this local variable to this
            new type.
            
            This will create a copy of the type provided in argument
            for avoiding problem with the IDA type system. For more
            informaiton see :class:`IdaType` .

            :param value: An object which inherit from :class:`IdaType` .
        """
        if not isinstance(value, biptype.IdaType):
            raise TypeError("HxLvar type setter expect an object which inherit from IdaType")
        if not self._lvar.set_lvar_type(value._get_tinfo_copy()):
            raise RuntimeError("Unable to set the type {} for this lvar {}".format(value.str, self.name))
        self._lvar.set_user_type()
        if self._persistent:
            self.save()

    def save(self):
        """
            Function which allow to save the change made to the local variable
            inside the idb. This is necessary because by default the change
            made to a lvar using the IDA interface only change the object in
            memory and not its content.
            
            This function is called by default by the setters of this object
            if the ``_persistent`` property is at True (the default). It
            should not be necessary to call this directly.
        """
        # object needed for containing the information to save about the lvar
        lsi = lvar_saved_info_t()
        # set everything which need to be save
        lsi.ll = self._lvar
        lsi.name = self.name
        lsi.type = self._lvar.tif
        lsi.size = self.size
        lsi.cmt = self.comment
        # create the object which is used for saving in the idb
        lvuv = lvar_uservec_t()
        if not lvuv.lvvec.add_unique(lsi): # adding this var to save
            raise RuntimeError("Unable to create object for saving the variable")
        # saving in the idb
        save_user_lvar_settings(self._hxcfunc.ea, lvuv)


    ################################ FLAGS ##################################

    @property
    def is_arg(self):
        """
            Property which return true if this local variable is an argument
            of this function, false otherwise.

            .. todo:: test

            :return: bool
        """
        return self._lvar.is_arg_var

    @is_arg.setter
    def is_arg(self, value):
        """
            Setter which allow to change if this local variable should be
            considered as an argument of this function.

            .. todo:: test

            :param bool value: If ``True`` this local variable will now be
                considered as an argument, if ``False`` this local variable
                will not be considered as an argument anymore. If this is not
                a boolean a ``TypeError`` will be raised.
        """
        if not isinstance(value, bool):
            raise TypeError("HxLvar.is_arg setter expect a boolean value")
        if value:
            self._lvar.set_arg_var()
        else:
            self._lvar.clr_arg_var()





