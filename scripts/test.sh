#!/bin/bash

printInfos() {
    echo -e "Usage: $0 [options]"
    echo -e "  -h, --help\t\tDisplay this help"
    echo -e "  -t, --test\t\tRun in test mode"
    echo -e "  -p, --pep8\t\tCheck pep8 syntax"
    echo -e "      --linemax <param>\tMaximum number of caracter per line that PEP8"
    echo -e "            \t\tneed to check (only if PEP8 is enable)"
    echo -e "  -d, --dead\t\tCheck for dead code"
    echo -e "  -m, --mypy\t\tCheck type of python code"
    echo -e "  -c, --clean\t\tClean (and remove) old docker images"
    echo -e "  -r, --run\t\tRun the ee-outlier (in interactive mode)"
}

execTest=0
checkPep=0
deadCode=0
checkType=0
execRun=0
cleanImg=0
haveLoop=0
change_pep8_max_line=0

PEP8_MAX_LINE=120

while [ -n "$1" ]; do # while loop starts
    haveLoop=1
    case "$1" in
    -t) execTest=1 ;;
    --test) execTest=1 ;;

    -p) checkPep=1 ;;
    --pep8) checkPep=1 ;;

    -d) deadCode=1 ;;
    --dead) deadCode=1 ;;

    -m) checkType=1 ;;
    --mypy) checkType=1 ;;

    -c) cleanImg=1 ;;
    --clean) cleanImg=1 ;;

    -r) execRun=1 ;;
    --run) execRun=1 ;;

    --linemax)
        change_pep8_max_line=1
        PEP8_MAX_LINE=$2
        shift
        ;;

    -h) printInfos ;;
    --help) printInfos ;;

    *)  echo "Unknow parameter $1"
        printInfos
        ;;
    esac
    shift
done

if (( $haveLoop == 0)); then
    echo "No parameters... So nothing execute"
    printInfos
    exit
fi

if (( $change_pep8_max_line == 1 && $checkPep == 0)); then
    echo "Change the max number of line but PEP8 check is not enable"
    exit
fi


echo "===== BUILD ====="
sudo docker build -t "outliers-dev" .
echo "=============="

if (( $execTest == 1)); then
    echo "===== TEST ====="
    sudo docker run -v "$PWD/defaults:/mappedvolumes/config" --name test-outliners -i outliers-dev:latest python3 outliers.py tests --config /defaults/outliers.conf
    echo "=============="
    echo "===== CLEAN ====="
    sudo docker rm test-outliners
    echo "=============="
fi

if (( $checkPep == 1)); then
    echo "===== PEP8 ====="
    if (( $change_pep8_max_line == 1)); then
        echo "Configuration: max-line-length=$PEP8_MAX_LINE"
    fi
    sudo docker run -v "$PWD/defaults:/mappedvolumes/config" --name test-outliners -i outliers-dev:latest flake8 --max-line-length=$PEP8_MAX_LINE /app
    echo "=============="
    echo "===== CLEAN ====="
    sudo docker rm test-outliners
    echo "=============="
fi

if (( $deadCode == 1)); then
    echo "===== DEAD CODE ====="
    sudo docker run -v "$PWD/defaults:/mappedvolumes/config" --name test-outliners -i outliers-dev:latest python3 -m vulture /app
    echo "=============="
    echo "===== CLEAN ====="
    sudo docker rm test-outliners
    echo "=============="
fi

if (( $checkType == 1)); then
    echo "===== CHECK TYPE ====="
    sudo docker run -v "$PWD/defaults:/mappedvolumes/config" --name test-outliners -i outliers-dev:latest mypy --strict /app/outliers.py
    echo "=============="
    echo "===== CLEAN ====="
    sudo docker rm test-outliners
    echo "=============="
fi

if (( $execRun == 1)); then
        echo "===== RUN INTERACT ====="
        # sudo docker run -v "$PWD/defaults:/mappedvolumes/config" -i outliers-dev:latest /bin/bash
        sudo docker run -v "$PWD/defaults:/mappedvolumes/config" --name test-outliners --network=sensor_network -i outliers-dev:latest python3 outliers.py interactive --config /defaults/outliers.conf
        #sudo docker run -v "$PWD/defaults:/mappedvolumes/config" -i outliers-dev:latest python3 outliers.py interactive --config /defaults/outliers.conf
        echo "=============="
        echo "===== CLEAN ====="
        sudo docker rm test-outliners
        echo "=============="
fi

if (( $cleanImg == 1)); then
        echo "===== CLEAN IMG ====="
        sudo docker rmi $(sudo docker images -f dangling=true -q)
        echo "=============="
fi

# python3 -m unittest discover tests/ test_*.py

