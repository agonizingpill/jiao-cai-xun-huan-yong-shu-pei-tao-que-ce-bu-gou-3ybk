import hashlib,json,itertools

def apriori(baskets,min_support=.15,min_confidence=.6):
    n=len(baskets)
    if not n:return[]
    items=sorted(set().union(*baskets));counts={};previous=set()
    for k in range(1,4):
        current=set()
        for combo in itertools.combinations(items,k):
            key=frozenset(combo)
            if k>1 and not all(frozenset(sub)in previous for sub in itertools.combinations(combo,k-1)):continue
            count=sum(key<=basket for basket in baskets)
            if count/n>=min_support:counts[key]=count;current.add(key)
        previous=current
        if not current:break
    rules=[]
    for itemset,count in counts.items():
        if len(itemset)<2:continue
        for rhs in sorted(itemset):
            lhs=itemset-{rhs};confidence=count/counts[lhs];lift=confidence/(counts[frozenset([rhs])]/n)
            if confidence>=min_confidence and lift>1:rules.append({'if_subjects':sorted(lhs),'then_subject':rhs,'support':round(count/n,4),'confidence':round(confidence,4),'lift':round(lift,4)})
    return sorted(rules,key=lambda r:(-r['lift'],-r['confidence'],r['then_subject']))
def _hash(*parts):return int(hashlib.sha256('|'.join(parts).encode()).hexdigest(),16)
def _holdout(source_class):return _hash('38',source_class)%100<25
def recommend(entries,subjects):
    entries=sorted(entries,key=lambda e:(e['source_class'],e['id']))
    train=[e for e in entries if not _holdout(e['source_class'])];te=[e for e in entries if _holdout(e['source_class'])]
    rules=apriori([set(e['subjects'])for e in train]);hit=0;covered=0;cases=[]
    for e in te:
        basket=sorted(set(e['subjects']))
        if not basket:continue
        hidden=basket[_hash('38','hidden',e['source_class'])%len(basket)];visible=set(basket)-{hidden}
        guesses={r['then_subject']for r in rules if set(r['if_subjects'])<=visible and r['then_subject']not in visible}
        hit+=hidden in guesses;covered+=bool(guesses)
        cases.append({'basket_id':e['id'],'basket_code':e['code'],'source_class':e['source_class'],'visible':sorted(visible),'hidden':hidden,'recommended':sorted(guesses),'hit':hidden in guesses})
    current=set(subjects);suggested=[r for r in rules if set(r['if_subjects'])<=current and r['then_subject']not in current]
    evaluated=len(cases)
    return {'algorithm':'Apriori train-only itemset support + association rules','seed':38,'split':'按来源班哈希分组，同班不跨训练/留出','train_rows':len(train),'holdout_rows':len(te),'train_basket_ids':[e['id']for e in train],'holdout_basket_ids':[e['id']for e in te],'used_basket_ids':sorted(e['id']for e in entries),'source_checksum':hashlib.sha256(json.dumps([[e['source_class'],sorted(set(e['subjects']))]for e in entries],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),'min_support':.15,'min_confidence':.6,'min_lift':1,'rules':rules,'suggestions':suggested,'input_subjects':sorted(current),'holdout_hidden_item_recall':round(hit/evaluated,4)if evaluated else 0,'holdout_recommendation_coverage':round(covered/evaluated,4)if evaluated else 0,'holdout_cases':cases}
