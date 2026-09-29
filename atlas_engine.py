"""Dataset-specific Horta-to-CCF conversion and MRN lookup used by the local GUI."""
import base64,io,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from data_bundle import DataBundle
MRN_IDS=[128,539,548,555]
MODE_LABELS={'affine':'Affine only','nonlinear':'Affine + nonlinear'}

class AtlasEngine:
    def __init__(self, data_root):
        self.bundle = DataBundle(data_root)
        self.datasets = self.bundle.datasets
        atlas = self.bundle.atlas
        self.annotation = np.load(self.bundle.path(atlas['annotation']), allow_pickle=False)
        if list(self.annotation.shape) != atlas['shape'] or self.annotation.dtype != np.uint32:
            raise ValueError('Unexpected annotation shape or data type.')
        self.fields = {}
        self.info = {0: {'name':'Outside annotated brain','acronym':'unassigned','ancestors':[],'color':'f4f6f8'}}
        def walk(n, parents):
            self.info[n['id']] = {'name':n['name'],'acronym':n['acronym'],'ancestors':parents,'color':n.get('color_hex_triplet','bfcbd1')}
            for child in n['children']:
                walk(child, parents + [n['id']])
        graph = json.loads(self.bundle.path(atlas['structures']).read_text(encoding='utf-8'))
        walk(graph['msg'][0], [])
        self.centers = np.load(self.bundle.path(atlas['mrn_centers']), allow_pickle=False)
        if self.centers.ndim != 2 or self.centers.shape[1] != 3 or not len(self.centers) or not np.isfinite(self.centers).all():
            raise ValueError('Invalid MRN voxel centers.')
        self.params = {}
        for name, ds in self.datasets.items():
            a = ds['affine']
            self.params[name] = (np.linalg.inv(np.asarray(a['matrix'],dtype=float)),
                                 np.asarray(a['translation'],dtype=float), np.asarray(a['center'],dtype=float))

    def field(self, dataset):
        if dataset not in self.fields:
            ds = self.datasets[dataset]
            f = np.load(self.bundle.path(ds['warp']), mmap_mode='r', allow_pickle=False)
            if list(f.shape) != ds['warp_shape'] or f.ndim != 4 or f.shape[-1] != 3 or f.dtype != np.float32:
                raise ValueError('Unexpected nonlinear field shape or data type.')
            self.fields[dataset] = f
        return self.fields[dataset]

    def convert(self,dataset,xyz,mode):
        if dataset not in self.datasets:raise ValueError('Choose a supported dataset.')
        ds=self.datasets[dataset]
        if mode not in ds['modes']:raise ValueError('That transform is unavailable for this dataset. No fallback was applied.')
        try:h=np.asarray(xyz,dtype=float)
        except (TypeError,ValueError):raise ValueError('Enter three numeric Horta coordinates.')
        if h.shape!=(3,) or not np.isfinite(h).all():raise ValueError('Enter exactly three finite Horta coordinates: X, Y, Z.')
        original=h/np.array(ds['native_voxel_um'])/ds['pyramid_factor']
        if np.any(original<0) or np.any(original>np.array(ds['original_shape_xyz'])-1):
            raise ValueError('These coordinates are outside this dataset’s image bounds. Check the dataset, units and coordinate order.')
        for axis, extent in ds['flip_axes'].items():
            original[int(axis)] = extent - original[int(axis)]
        moving=original*np.array(ds['resample']);inv,t,c=self.params[dataset]
        q=(moving-c-t)@inv.T+c;affine=q*ds['resolution_um'];mapped=affine.copy()
        if mode=='nonlinear':
            field = self.field(dataset)
            if np.any(q<0) or np.any(q>=np.array(field.shape[:3])-1):
                raise ValueError('Point is outside the nonlinear field. Choose Affine only explicitly to inspect the affine estimate.')
            lo=np.floor(q).astype(int);frac=q-lo;d=np.zeros(3)
            for x in (0,1):
                for y in (0,1):
                    for z in (0,1):
                        off=np.array([x,y,z]);weight=np.prod(np.where(off,frac,1-frac))
                        d+=field[tuple(lo+off)]*weight
            if not np.isfinite(d).all():
                raise ValueError('The nonlinear field contains invalid values at this location.')
            mapped=(q+d)*ds['resolution_um']
        return mapped,affine

    def label(self,q):
        idx=np.rint(q/25).astype(int)
        if np.any(idx<0) or np.any(idx>=np.array(self.annotation.shape)):return None
        return int(self.annotation[tuple(idx)])

    @staticmethod
    def box_distance(q,centers):
        d=np.maximum(np.abs(centers-q)-12.5,0);sq=np.einsum('ij,ij->i',d,d);i=int(np.argmin(sq))
        return float(np.sqrt(sq[i])),np.clip(q,centers[i]-12.5,centers[i]+12.5)

    def boundary_distance(self,q,inside):
        if not inside:return self.box_distance(q,self.centers)
        idx=np.rint(q/25).astype(int);lo=np.maximum(idx-40,0);hi=np.minimum(idx+41,self.annotation.shape)
        crop=self.annotation[tuple(slice(a,b) for a,b in zip(lo,hi))]
        centers=(np.argwhere(~np.isin(crop,MRN_IDS))+lo)*25.
        distance,near=self.box_distance(q,centers)
        if distance>=975:raise RuntimeError('Interior boundary search radius exceeded.')
        return distance,near

    def check(self,dataset,xyz,mode):
        q,affine=self.convert(dataset,xyz,mode);sid=self.label(q);aid=self.label(affine);inside=sid in MRN_IDS
        distance,near=self.boundary_distance(q,inside)
        region=self.info.get(sid,{'name':'Outside atlas volume','acronym':'out-of-volume'})
        result={'dataset':dataset,'horta_xyz_um':list(map(float,xyz)),'mode':mode,'transform_label':MODE_LABELS[mode],
                'data_bundle':self.bundle.bundle_id,'registration':self.datasets[dataset]['registration'],'ccf_ap_dv_ml_um':q.tolist(),
                'atlas_id':sid,'atlas_name':region['name'],'atlas_acronym':region['acronym'],
                'inside_mrn':inside if sid is not None else None,'outside_atlas_volume':sid is None,
                'boundary_distance_um':distance,'boundary_distance_kind':'inside clearance' if inside else 'outside distance',
                'nearest_mrn_boundary_ccf_um':near.tolist(),'within_100um_of_boundary':distance<=100,
                'hemisphere':'Lower CCF ML' if q[2]<self.bundle.atlas['midline_ml_um'] else 'Higher CCF ML',
                'affine_ccf_ap_dv_ml_um':affine.tolist(),'nonlinear_shift_um':float(np.linalg.norm(q-affine)),
                'affine_atlas_id':aid,'affine_inside_mrn':aid in MRN_IDS,
                'atlas':'Allen CCFv3 2017 annotation, 25 µm','note':self.datasets[dataset]['note'],
                'caveat':'An atlas assignment is an estimate. Boundary distance is not an estimate of registration error. Anatomical left/right is unverified.'}
        result['slices']=self.slices(q) if sid is not None else []
        return result

    def slices(self,q):
        idx=np.rint(q/25).astype(int);out=[]
        # rows increase in DV for coronal/sagittal; horizontal rows increase in AP.
        for title,fixed,row,col in [('Coronal',0,1,2),('Sagittal',2,1,0),('Horizontal',1,0,2)]:
            sl=np.take(self.annotation,idx[fixed],axis=fixed)
            remaining=[j for j in range(3) if j!=fixed]
            if remaining!=[row,col]:sl=sl.T
            rgb=np.empty((*sl.shape,3),dtype=np.uint8)
            for sid in np.unique(sl):
                info=self.info.get(int(sid),self.info[0]);color=np.array([int(info['color'][k:k+2],16) for k in (0,2,4)])
                color=(color*.25+np.array([235,239,240])*.75).astype(np.uint8)
                if sid==0:color=np.array([251,252,253])
                if sid in MRN_IDS:color=np.array([229,178,61])
                if sid==214:color=np.array([194,164,206])
                rgb[sl==sid]=color
            image=Image.fromarray(rgb).resize((sl.shape[1]*2,sl.shape[0]*2),Image.Resampling.NEAREST)
            draw=ImageDraw.Draw(image);px=(q[col]/25+.5)*2;py=(q[row]/25+.5)*2
            for color,width in [('white',5),('#087a86',2)]:
                draw.line((px-15,py,px-6,py),fill=color,width=width);draw.line((px+6,py,px+15,py),fill=color,width=width)
                draw.line((px,py-15,px,py-6),fill=color,width=width);draw.line((px,py+6,px,py+15),fill=color,width=width)
            draw.ellipse((px-4,py-4,px+4,py+4),fill='#087a86',outline='white',width=1)
            buf=io.BytesIO();image.save(buf,format='PNG')
            out.append({'title':title,'fixed_axis':['AP','DV','ML'][fixed],'fixed_um':int(idx[fixed]*25),
                        'horizontal_axis':['AP','DV','ML'][col],'vertical_axis':['AP','DV','ML'][row],
                        'image':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()})
        return out
