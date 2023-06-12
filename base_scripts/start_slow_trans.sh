
function start_slow() {
    id_name=$1
    echo $id_name
    succ_flag="succ_flag_dir/${id_name}"
    if [ -f "$succ_flag" ]; then
        echo "succ_flag file is exists: "${succ_flag}
    else
        python base_scripts/slow_trans.py ${id_name}
        if [ $? -eq 0 ];then
            touch $succ_flag
            echo "rob ticket successfully"
        fi
    fi
}


if [ ! -d "./succ_flag_dir" ]; then
    mkdir ./succ_flag_dir
fi

id_names=`grep -v '^[[:space:]]' base_scripts/slow_config.yaml|grep ":"|awk -F":" '{print $1}'`

for word in $id_names; do
    start_slow "$word" &
done

wait
