
id_name=$1
curl ifconfig.me
pip install ddddocr
# hadoop fs -get hdfs://R2/projects/rcmd_feature/hdfs/user/yunan.chen/py_env_20230603.tar.gz ./
# tar -xzvf py_env_20230603.tar.gz
# conda deactivate
# ls
# ls -l bin/activate
# source bin/activate
# which python

hadoop fs -test -e hdfs://R2/projects/rcmd_feature/hdfs/user/yunan.chen/hk_book/id_name/$id_name
if [ $? -ne 0 ];then
    python ./base_scripts/slow_trans.py $id_name
    if [ $? -eq 0 ];then
        hadoop fs -touchz hdfs://R2/projects/rcmd_feature/hdfs/user/yunan.chen/hk_book/id_name/$id_name
        echo "rob ticket successfully"
    fi
else
    echo "hdfs file is exists: hdfs://R2/projects/rcmd_feature/hdfs/user/yunan.chen/hk_book/id_name/"${id_name}
fi


