POLICIES=('first','prefer','strict')

def policyName(index):return POLICIES[index] if 0<=index<len(POLICIES) else 'first'

def policyIndex(policy):
    try:return POLICIES.index(policy)
    except ValueError:return 0

def decision(policy,matched,hasTemplates,refreshes,maxRefresh):
    if matched:return 'select'
    if policy=='first':return 'first'
    if not hasTemplates:return 'stop' if policy=='strict' else 'first'
    if refreshes<maxRefresh:return 'refresh'
    return 'first' if policy=='prefer' else 'stop'

def canStart(policy,hasTemplates):return policy!='strict' or bool(hasTemplates)
