import re
from progress.bar import Bar

################################################################################

def set_collation_types(byc):

    if byc["args"].collationtypes:
        s_p = {}
        for p in re.split(",", byc["args"].collationtypes):
            if p in byc["filter_definitions"].keys():
                if byc["filter_definitions"]["p"].get("collationed", True) is False:
                    continue
                s_p.update({p:byc["filter_definitions"][p]})
        if len(s_p.keys()) < 1:
            print("No existing collation type was provided with -c ...")
            exit()

        byc.update({"filter_definitions":s_p})

    return byc

################################################################################

def hierarchy_from_file(ds_id, coll_type, pre_h_f, byc):

    coll_defs = byc["filter_definitions"][coll_type]
    hier = { }

    f = open(pre_h_f, 'r+')
    h_in  = [line for line in f.readlines()]
    f.close()

    parents = [ ]

    no = len(h_in)
    bar = Bar(coll_type, max = no, suffix='%(percent)d%%'+" of "+str(no) )

    for c_l in h_in:

        bar.next()

        c, l, d, i = re.split("\t", c_l.rstrip() )
        d = int(d)

        max_p = len(parents) - 1
        if max_p < d:
            parents.append(c)
        else:
            # if recursing to a lower column/hierarchy level, all deeper "parent" 
            # values are discarded
            parents[ d ] = c
            while max_p > d:
                parents.pop()
                max_p -= 1

        l_p = { "order": i, "depth": d, "path": parents.copy() }

        if not c in hier.keys():
            hier.update( { c: { "id": c, "label": l, "hierarchy_paths": [ l_p ] } } )
        else:
            hier[ c ]["hierarchy_paths"].append( l_p )

    bar.finish()

    return hier
