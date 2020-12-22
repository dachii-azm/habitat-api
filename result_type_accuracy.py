from result_vqa import q_result_list


type_list = ['location', 'color', 'color_room', 'next_to', 'next_to_room', 'on', 'on_room', 'above', 'below', 'below_room']
type_cor_cnt = [0 for i in range(len(type_list))]
type_cnt = [0 for i in range(len(type_list))]

for i in range(len(q_result_list)):
    index = type_list.index(q_result_list[i][3])
    if q_result_list[i][1]==q_result_list[i][2]:
        type_cor_cnt[index] += 1
    
    type_cnt[index] += 1

for j in range(len(type_cnt)):
    print(str(type_list[j])) 
    print("sum: " + str(type_cnt[j]))
    if type_cnt[j] != 0:
        print("accuracy: " + str((float(type_cor_cnt[j])*100)/float(type_cnt[j])))
    else:
        print("question is not found")
    
