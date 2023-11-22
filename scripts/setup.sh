# run from COMET/
cd XED-to-XML
./mfile.py --opt=2 --no-encoder pymodule || exit 1
cp xed.* ..
cd ..

wget https://www.uops.info/instructions.xml || exit 1
./scripts/convertXML.py instructions.xml || exit 1
rm instructions.xml
