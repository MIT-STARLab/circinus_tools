def index_from_key(iterable,key,value):
    """ this is an augmented list index() function that allows index lookup with an arbitrary key function"""
    #  I don't think there's a built-in for this in Python? list.index() doesn't allow for checking with an arbitrary key function....
    indx =  next((indx for indx,item in enumerate(iterable) if key(item) == value), None)

    if indx is None:
        raise ValueError('%s is not in input'%(value))

    return indx
