#!/usr/bin/env python2

class CodeBuilder(object):
    """
        Simple class for building indented code blocks.
    """

    def __init__(self, code='', indent="    "):

        #assume an initial indent level of zero
        self.indent_level = 0

        #and store the given indent
        self.indent = indent

        #start off with an empty block of code
        self.code = code + '\n'

    def __repr__(self):
        return self.code

    def get_code(self):
        return self.code

    def get_indent(self):
        return (self.indent * self.indent_level)

    def __iadd__(self, line):

        #add the given line, properly formatted at the given indent level
        self.code += self.get_indent() + line + "\n"
        return self

    def add(self, lines):
        """
            Adds one or more lines to the code block.
            For single lines, use the normal += concatination syntax.
        """

        #if this isn't a list, wrap it in one
        if not isinstance(lines, list):
            lines = [lines]

        #add each line to the code
        for line in lines:
            self += line

    def start_block(self, line=''):

        #add the given line to the code...
        self += line

        #and increase the indent level
        self.indent_level += 1;

    def end_block(self, line= ''):

        #decrease the indent level
        self.indent_level -= 1

        #add the given line to the code...
        self += line

    def add_inset(self, line):
        """
            Adds a line which is inset by a single indent level.
        """
        self.code += (self.indent * (self.indent_level - 1)) + line + "\n"


class JSBuilder(CodeBuilder):

    def add_call(self, name, *args):
        self += name + '(' + ','.join(args) + ');'


class VHDLBuilder(CodeBuilder):

    def use_std_logic(self):
        """
            Adds the pre-amble neccessary to use the IEEE 1164 std logic library.
        """
        self += "library IEEE;"
        self += "use IEEE.STD_LOGIC_1164.all;"
        self += ''


    def add_entity(self, name, inputs, outputs):
        """
            Adds an entity to the buffer's output.
            TODO: support generics?
        """

        #create a list that contains each input and output, with its type
        io = ([i + ' : in std_logic' for i in inputs] + [o + ' : out std_logic' for o in outputs])

        #start a new entity/port
        self.start_block("entity " + name + " is ")
        self.start_block("port(");

        #add each of the inputs and outputs
        separator = (";\n" + self.get_indent())
        self += separator.join(io)

        #and end the entity
        self.end_block(");")
        self.end_block("end entity;")

    def add_architecture(self, entity_name, body, preamble=None, architecture_name="behavioral"):

        #add the architecture
        self.start_architecture(entity_name, architecture_name, preamble)
        self.add(body)
        self.end_architecture()


    def start_architecture(self, entity_name, architecture_name="behavioral", preamble=None):
        #start the architecture
        self.start_block("architecture " + architecture_name + " of " + entity_name + " is")

        #if we have a pre-amble, add it
        if preamble:
            self.add(preamble)

        #and add the "begin" that delimits the body of the architecture
        self.add_inset("begin")

    def end_architecture(self):
        self.end_block("end architecture;")
