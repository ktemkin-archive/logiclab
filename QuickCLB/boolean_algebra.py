#!/usr/bin/env python2

import operator
import pyparsing
import collections
from code_builder import VHDLBuilder

class InvalidExpressionException(Exception):
    pass

class CombinationalFeedbackException(InvalidExpressionException):
    pass


class LogicExpression(object):

    def __init__(self, ast, inputs=None):
        self.ast = ast

        #if inputs were provided, use them; otherwise, determine the inputs from the ast
        self.inputs = inputs if inputs else self._inputs_from_ast()

    @classmethod
    def from_boolean_algebra(cls, algebra_notation, inputs=None):
        """
            Generates a new LogicExpression from a Boolean Algebra notation.
        """

        #convert the boolean algebra to an abstract syntax tree
        ast = cls._algegbra_to_ast(algebra_notation, inputs)

        #Convert the AST into a LogicExpression.
        #Note that we don't use the inputs provided; this allows us to remove
        #unused inputs from the expression.
        return cls(ast)


    def to_VHDL(self):
        return self.ast_to_VHDL(self.ast)

    def _inputs_from_ast(self):
        """
        """

        #extract each of the unique symbols from the expression
        asl = set(self._flatten([self.ast]))

        #remove any logic symbols that exist in the string
        return asl.difference(set(('*', '\'', '+', '^')))


    @classmethod
    def _flatten(cls, l):
        """
            Method from:
            http://stackoverflow.com/questions/2158395/flatten-an-irregular-list-of-lists-in-python
        """

        for el in l:
            if isinstance(el, collections.Iterable) and not isinstance(el, basestring):
                for sub in cls._flatten(el):
                    yield sub
            else:
                yield el


    @staticmethod
    def _algebra_to_ast(algebra_notation, inputs=None):
        """
            Converts a Boolean Algebra expression to an abstract syntax tree.
        """

        #convert each of the VHDL input terms into a grammar literal
        if inputs:
            inputTerms = reduce(lambda x, y : x | pyparsing.Literal(y.strip()), inputs)
        else:
            #create a basic identifier grammar element
            IdentifierChars = pyparsing.alphanums + '_[]'
            inputTerms = pyparsing.Word(IdentifierChars)

        #define the algebra operators, in order of precedence
        algebraOperators = \
            [
                ("'", 1, pyparsing.opAssoc.LEFT), #NOT
                (pyparsing.Optional("*", default='*'), 2, pyparsing.opAssoc.LEFT), #AND, including implied AND
                ("+", 2, pyparsing.opAssoc.LEFT), #OR
                ("^", 2, pyparsing.opAssoc.LEFT)  #XOR
            ]

        #define a new grammar in terms of the input terms and algebraic operators
        algebraExpresion = pyparsing.operatorPrecedence(inputTerms, algebraOperators)

        #use the newly created grammar to convert the boolean expression into an abstract syntax list
        try:
            ast = algebraExpresion.parseString(algebra_notation)[0]
        except pyparsing.ParseException, e:
            raise InvalidExpressionException("I couldn't figure out what you meant by '" + algebra_notation + "'.")

        #remove the PyParsing object wrapper from the list
        if isinstance(ast, pyparsing.ParseResults):
            ast = ast.asList()

        return ast

    def evaluate(self, input_map):
        """
            Evaluates the expression for the given input set.
        """
        return self.evaluate_ast(self.ast, input_map)

    @classmethod
    def _evaluate_ast(cls, ast, input_map):
        """
            Evaluates the given AST, and returns a boolean.
        """

        #base case: we've been given a boolean; return it directly
        if isinstance(ast, bool):
            return ast

        #base case: we've reached a leaf in the abstract syntax tree
        #evaluate it from the input map
        #TODO: handle KeyError more nicely?
        if not isinstance(ast, list):
            return input_map[ast]

        #recursive case 1: unary operator (i.e. NOT)
        if ast[1] == "'":
            return not cls._evaluate_ast(ast[0])

        #get the operator that corresponds to the correct VHDL opereation
        op = {'*': operator.and_, '+': operator.or_, '^':operator.xor_ }.get(ast[1])

        #compute the value of each item in the list by recursing
        values = [cls._evaluate_ast(item) for item in ast if item != ast[1]]

        #apply the operator to each of the values
        return reduce(op, values)

    @classmethod
    def ast_to_VHDL(cls, ast):

        #base case: we've reached a leaf in the abstract syntax tree
        if not isinstance(ast, list):
            return ast

        #recursive case 1: unary operator (e.g. NOT)
        if ast[1] == "'":
            return 'not ' + cls.ast_to_VHDL(ast[0])

        #recursive case 2: binary operator
        buf = '('

        #get the VHDL keyword that corresponds to the given operator
        op = {'*': ' and ', '+': ' or ', '^':' xor ' }.get(ast[1])

        #and replace each instance of the operator with the appropriate VHDL construct
        for i in ast:
            buf += op if i == ast[1] else cls.ast_to_VHDL(i)

        return buf + ')'



class LogicEquation(LogicExpression):
    """
        Represents a combinational logic _equation.
    """

    def __init__(self, ast, output, inputs=None):
        self.output = output
        super(LogicEquation, self).__init__(ast)

    def to_VHDL(self):

        #get the right-hand side of the equation from the parent class
        rhs = super(LogicEquation, self).to_VHDL()

        #and add the appropriate assignment
        return self.output + " <= " + rhs + ';'

    @classmethod
    def from_boolean_algebra(cls, algebra_notation, inputs=None):

        #if we didn't have exactly one assignment, this isn't a valid expression
        if algebra_notation.count('=') != 1:
            raise InvalidExpressionException("I couldn't figure out what you meant by '" + algebra_notation + "'")

        #split the expression into its output and core expression
        output, expression = algebra_notation.split('=')

        #convert the RHS of the expression into an abstract syntax tree
        ast = cls._algebra_to_ast(expression)

        #and return a new LogicEquation
        return cls(ast, output, None)



class CombinationalLogicBlock(object):
    """
        Represents a block of arbitrary combinational logic.
    """

    def __init__(self, equations, outputs=None, inputs=None):
        self.equations = equations

        #if inputs/outputs were provided, use them; otherwise, derive them automatically
        self.outputs = outputs if outputs else self._outputs_from_equations();
        self.inputs = inputs if inputs else self._inputs_from_equations();

        #check to ensure that no signal is used as both an input and output
        both = self.outputs.intersection(self.inputs)
        if both:
            raise CombinationalFeedbackException("Cannot use a variable as both an output and an input! (" + repr(both) + ")")


    def _inputs_from_equations(self):
        """
        """

        #build a set which contains all inputs from each of the contained expressions
        inputs = set()
        for equation in self.equations:
            inputs.update(equation.inputs)

        #and return it
        return inputs


    def _outputs_from_equations(self):
        """
            Automatically determines the set of outputs for this CLB from its equations.
        """

        #build a set which contains all outputs from the contained expressions
        outputs = set()
        for equation in self.equations:
            outputs.add(equation.output)

        #and return it
        return outputs


    @classmethod
    def from_boolean_algebra(cls, equations):

        #if we have an instance of a file object, conver the file into a set of equations
        if isinstance(equations, file):
            equations = cls._equations_from_file(equations)

        #convert each of the equations to a logic expression
        equations = [LogicEquation.from_boolean_algebra(equation) for equation in equations]

        #and convert those equations to a CombinationalLogicBlock
        return cls(equations)


    @classmethod
    def _equations_from_file(cls, eqfile):

        #start an array of expressions, which contains the first line in the file
        eqs = []

        #reach each of the lines in the equation file
        for line in eqfile.readlines():

            line = line.replace("\n", ' ')

            #skip blank lines
            if not line.strip():
                continue

            #if this line starts a new equation, add it to the next element of the list
            if '=' in line:
                eqs.append(line)
            else:
                eqs[-1] += line

        #return the created set of equations
        return eqs

    def to_VHDL(self, entity_name):

        buf = VHDLBuilder()
        buf.use_std_logic()

        #add the relevant entity to the VHDL output
        buf.add_entity(entity_name, self.inputs, self.outputs)
        buf += ''

        #get the VHDL code for each of the internal equations
        body = [eq.to_VHDL() for eq in self.equations]

        #and create the body of the VHDL element
        buf.add_architecture(entity_name, body)

        #return the newly-created VHDL code
        return buf





