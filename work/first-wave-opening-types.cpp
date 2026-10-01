struct OpeningKey
{
    int owner,operation,army;
    OpeningKey(int o,int p,int a):owner(o),operation(p),army(a){}
    bool operator<(const OpeningKey& b)const{return owner!=b.owner?owner<b.owner:operation!=b.operation?operation<b.operation:army<b.army;}
};
struct OpeningForecast
{
    int turn,target,enemy,domain,filled,hp,strength;bool visible,ready,complete;
    std::vector<AssaultWaveUnit> rows;
    OpeningForecast():turn(-1),target(-1),enemy(-1),domain(-1),filled(-1),hp(-1),strength(-1),visible(false),ready(false),complete(false){}
};
static std::map<OpeningKey,OpeningForecast> openingForecasts;
static int openingForecastTurn=-1;
