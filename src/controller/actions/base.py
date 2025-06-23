""" ActionBase module  """

class ActionBase:
    """ ActionBase class """
    conditions = {}
    reactions = {}
    weights = {}

    g = None  # goal; involved in plan costs
